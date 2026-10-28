import os
import clr
import math

dwsim_path=r"C:\Users\manud.DESKTOP-S9D0MNC\AppData\Local\DWSIM"

os.environ["PATH"]=dwsim_path+os.pathsep+os.environ["PATH"]

clr.AddReference(os.path.join(dwsim_path, "DWSIM.Automation.dll"))

from DWSIM.Automation import Automation3

aut = Automation3()

Flowsheet = aut.LoadFlowsheet(r"C:\Users\manud.DESKTOP-S9D0MNC\OneDrive\Documents\DWSIM Application Data\Distillation_design.dwxmz")

#Loading the Streams and Columns
feed = Flowsheet.GetFlowsheetSimulationObject("Feed").GetAsObject()
distillate = Flowsheet.GetFlowsheetSimulationObject("Distillate").GetAsObject()
bottoms = Flowsheet.GetFlowsheetSimulationObject("Bottoms").GetAsObject()
column = Flowsheet.GetFlowsheetSimulationObject("Rigorous Column").GetAsObject()
shortcut_feed=Flowsheet.GetFlowsheetSimulationObject("S-Feed").GetAsObject()
shortcut_column=Flowsheet.GetFlowsheetSimulationObject("Shortcut Column").GetAsObject()

# Feed Properties
feed.Empty()
T=float(input("Enter the Feed Temperature(C):"))
P=float(input("Enter the Pressure(bar):"))
M=float(input("Enter the Molar Flow rate of Feed(mol/s):"))
T=T+273.15
P=P*100000
feed.SetTemperature(T)
feed.SetPressure(P)
feed.SetMolarFlow(M)
shortcut_feed.SetTemperature(T)
shortcut_feed.SetPressure(P)
shortcut_feed.SetMolarFlow(M)
C=[]
x=[]

while True:
    C = []
    x = []
    while True:
        Compound = input("Enter Component:")
        X = float(input("Enter Composition:"))
        if X <= 0 or X > 1:
            print("Composition must be greater than 0 and at most 1.")
            continue
        C.append(Compound)
        x.append(X)
        total = sum(x)
        if math.isclose(total,1.0,abs_tol=1e-6):
            break
        if total > 1.0:
            print("Total exceeds 1. Enter the composition again.")
            break
    if math.isclose(sum(x),1.0,abs_tol=1e-6):
        break


for name in [str(k) for k in Flowsheet.SelectedCompounds.Keys]:
    if name not in C:
        print("Removing leftover compound:", name)
        Flowsheet.SelectedCompounds.Remove(name)

existing = [str(k) for k in Flowsheet.SelectedCompounds.Keys]
for compound in C:
    if compound not in existing:
        print("Adding:", compound)
        Flowsheet.AddCompound(compound)
bps={}

for name, compound in Flowsheet.SelectedCompounds.items():
    bps[name]=compound.Normal_Boiling_Point

lightest = None
for name in bps:
    if lightest is None or bps[name] < bps[lightest]:
        lightest = name
heaviest = None
for name in bps:
    if heaviest is None or bps[name]>bps[heaviest]:
        heaviest = name

for ms in (feed, distillate, bottoms,shortcut_feed):
    for phase in ms.Phases.Values:
        phase.Compounds.Clear()
    Flowsheet.AddCompoundsToMaterialStream(ms)

# Desired Separation and Desired Component
component=input("Enter the Desired Component:")
desired_purity=float(input("Enter the desired purity(%):"))
Product_flow=float(input("Enter the Product Flow rate required(mol/s):"))

for i in range(len(C)):
    MolarFlow=x[i]*M
    if C[i] == component:
        Feed_fraction=x[i]
    feed.SetOverallCompoundMolarFlow(C[i],MolarFlow)
    shortcut_feed.SetOverallCompoundMolarFlow(C[i],MolarFlow)

print("Flow(mol/s) =", feed.GetMolarFlow())
print("Composition =", list(feed.GetOverallComposition()))


if not 0 < Product_flow < M:
    raise ValueError("Product flow must be between 0 and feed flow.")
desired_purity=desired_purity/100

if Product_flow*desired_purity >= M*Feed_fraction:
    raise ValueError("Required Flow is Greater than Supplied flow")

desired_product = component
best_purity=desired_purity

if desired_product not in bps:
    raise ValueError("Desired component is not in the feed.")
if desired_product==lightest:
    product="distillate"
    Bottom_flow = M-Product_flow
    column.SetReboilerSpec("Product Molar Flow Rate", Bottom_flow, "mol/s")
elif desired_product==heaviest:
    product="bottoms"
    Bottom_flow = Product_flow
    column.SetReboilerSpec("Product Molar Flow Rate", Bottom_flow, "mol/s")
else :
    product=input("Enter the location of desired product(distillate/bottoms):").strip().lower()
    if product=="distillate":
        Bottom_flow = M-Product_flow
        column.SetReboilerSpec("Product Molar Flow Rate",Bottom_flow,"mol/s")
    else:
        Bottom_flow = Product_flow
        column.SetReboilerSpec("Product Molar Flow Rate", Bottom_flow, "mol/s")

if product not in ("distillate", "bottoms"):
    raise ValueError("Enter distillate or bottoms.")

# Getting the Minimum reflux and Minimum stages required from shortcut column
sorted_comp=sorted(bps ,key = bps.get)
product_index=sorted_comp.index(desired_product)
if desired_product == sorted_comp[0]:
    light_key=sorted_comp[0]
    heavy_key=sorted_comp[1]
elif desired_product == sorted_comp[-1]:
    light_key=sorted_comp[-2]
    heavy_key=sorted_comp[-1]
else:
    if product == "distillate":
        light_key=desired_product
        heavy_key=sorted_comp[product_index+1]
    else:
        light_key=sorted_comp[product_index-1]
        heavy_key=desired_product

shortcut_column.m_lightkey = light_key
shortcut_column.m_heavykey = heavy_key

impurity=1-desired_purity
shortcut_column.SetPropertyValue("PROP_SC_1",impurity)
shortcut_column.SetPropertyValue("PROP_SC_2",impurity)

aut.CalculateFlowsheet(Flowsheet,None)

Rmin=shortcut_column.GetPropertyValue("PROP_SC_5")
min_stages=int(shortcut_column.GetPropertyValue("PROP_SC_6"))
opt_feed_stage=int(shortcut_column.GetPropertyValue("PROP_SC_7"))

print("Minimum Reflux =", Rmin)
print("Minimum Stages required =", min_stages)
print("Optimum feed stage =", opt_feed_stage)

#Choosing the Required Optimization
optimization = input(
    "Choose optimization:\n"
    "1. Minimum Stages\n"
    "2. Minimum Reflux\n"
    "Enter choice: "
)

reflux = 1.05*Rmin
max_reflux = 2.0*Rmin
reflux_step=0.1*Rmin
purity_achieved=0
stage_achieved=0
feed_stage_achieved=0
reflux_achieved=0
solution_found=False
purity_reached=False
purity=0
tol=0.001
tol_limit=3
stage_best_purity=0

#Iterates the Reflux first and then Stages
if optimization=="1":
    for stages in range(min_stages, 31):
        if not solution_found:
            prev_purity = 0
            tol_count = 0
            reflux=1.05*Rmin
            while reflux <= max_reflux:
                print("Testing Reflux =", reflux)
                conv_started = False
                Failure_count = 0
                stage_best_purity = 0
                stage_best_feed_stage = None
                for feed_stage in range(opt_feed_stage, stages):

                    column.SetPropertyValue("PROP_DC_7", stages)
                    column.SetPropertyValue("Condenser_Specification_Value", reflux)
                    column.SetStreamFeedStage(feed, feed_stage)

                    aut.CalculateFlowsheet(Flowsheet, None)

                    if not column.Calculated:
                        print("Column Not Converged")
                        Failure_count += 1
                        if conv_started and Failure_count >= 2:
                            print("Error =", column.ErrorMessage)
                            print("Stopping feed-stage search.")
                            break

                    if column.Calculated:
                        print("Column Converged")
                        print("Number of Stages:", stages)
                        print("Feed Stage:", feed_stage+1)
                        Failure_count = 0
                        purity=0
                        conv_started = True

                        if product == "distillate":
                            names = distillate.GetCompoundNames()
                            composition = distillate.GetOverallComposition()
                            print("Distillate Composition:")
                            for i in range(len(names)):
                                if names[i] == desired_product:
                                    purity = composition[i]
                                    print(desired_product,":", purity)
                        else:
                            compounds = bottoms.GetCompoundNames()
                            comp = bottoms.GetOverallComposition()
                            print("Bottom Product Composition:")
                            for i in range(len(compounds)):
                                if compounds[i] == desired_product:
                                    purity = comp[i]
                                    print(desired_product,":", purity)
                        if purity >= stage_best_purity:
                            stage_best_purity = purity
                            stage_best_feed_stage = feed_stage+1

                if stage_best_purity >= desired_purity:
                    purity_achieved = stage_best_purity
                    feed_stage_achieved = stage_best_feed_stage
                    stage_achieved = stages
                    reflux_achieved = reflux
                    solution_found = True
                    break

                reflux += reflux_step
            if solution_found:
                break

#Iterates the Stages first and then Reflux
elif optimization=="2":
    while reflux <= max_reflux and not solution_found:
        prev_purity = 0
        tol_count = 0
        print("Testing Reflux =", reflux)

        for stages in range(min_stages, 31):
            print("Testing Stage:", stages)
            conv_started = False
            Failure_count = 0
            stage_best_purity = 0
            stage_best_feed_stage = None
            for feed_stage in range(opt_feed_stage, stages):
                print("Testing Feed Stage:", feed_stage+1)
                column.SetPropertyValue("PROP_DC_7", stages)
                column.SetPropertyValue("Condenser_Specification_Value", reflux)
                column.SetStreamFeedStage(feed, feed_stage)

                aut.CalculateFlowsheet(Flowsheet, None)

                if not column.Calculated:
                    print("Column Not Converged")
                    Failure_count += 1
                    if conv_started and Failure_count >= 2:
                        print("Error =", column.ErrorMessage)
                        print("Stopping feed-stage search.")
                        break

                if column.Calculated:
                    Failure_count = 0
                    conv_started = True
                    purity=0
                    if product == "distillate":
                        names = distillate.GetCompoundNames()
                        composition = distillate.GetOverallComposition()
                        for i in range(len(names)):
                            if names[i] == desired_product:
                                purity = composition[i]
                                print(desired_product,":", purity)
                    else:
                        compounds = bottoms.GetCompoundNames()
                        comp = bottoms.GetOverallComposition()
                        print("Bottom Product Composition:")
                        for i in range(len(compounds)):
                            if compounds[i] == desired_product:
                                purity = comp[i]
                                print(desired_product,":", purity)

                    if purity >= stage_best_purity:
                        stage_best_purity = purity
                        stage_best_feed_stage = feed_stage+1

            if stage_best_purity >= desired_purity:
                purity_achieved = stage_best_purity
                feed_stage_achieved = stage_best_feed_stage
                stage_achieved = stages
                reflux_achieved = reflux
                solution_found = True
                break

            #To prevent the iterating of Stages if the Improvement is not much for next stage
            if stage_best_purity > 0:
                improvement = stage_best_purity - prev_purity
                if improvement < tol:
                    tol_count += 1
                    if tol_count >= tol_limit:
                        break
                else:
                    tol_count = 0
                prev_purity = stage_best_purity
        if not solution_found:
            reflux += reflux_step

else:
    raise ValueError("Invalid optimization method")


print("----- FINAL RESULT -----")

if solution_found:
    print("****** Configuration Achieving Desired Purity ******")
    print("Desired Purity =", desired_purity)
    print("Purity Achieved =", purity_achieved)
    print("Optimum Reflux =", reflux_achieved)
    print("Feed Stage =", feed_stage_achieved)
    print("Number of Stages =", stage_achieved)

    column.SetPropertyValue("PROP_DC_7", stage_achieved)
    column.SetPropertyValue("Condenser_Specification_Value",reflux_achieved)
    column.SetStreamFeedStage(feed, feed_stage_achieved)
    aut.CalculateFlowsheet(Flowsheet, None)
    if column.Calculated:
        Reboiler_Heat_Duty=column.GetPropertyValue("PROP_DC_6")
        Condenser_Heat_Duty=column.GetPropertyValue("PROP_DC_5")
        print("Condenser Heat Duty(kW) =", Condenser_Heat_Duty)
        print("Reboiler Heat Duty(kW ) =", Reboiler_Heat_Duty)
        Estimated_Height = column.GetPropertyValue("Estimated Height")
        Estimated_Diameter = column.GetPropertyValue("Estimated Diameter")
        print("Estimated Column Height (m) =", Estimated_Height/1000)
        print("Estimated Column Diameter (m) =", Estimated_Diameter/1000)
    else:
        print("Final simulation did not converge. Heat duties unavailable.")

else:
    print("Desired purity was not achieved ", "within the specified reflux range.")
    print("Reflux Tested Up To =", max_reflux)

print("Calculation finished")