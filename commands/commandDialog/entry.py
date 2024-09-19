import traceback
import adsk.core
import adsk.fusion
import os
from ...lib import fusionAddInUtils as futil
from ... import config

app = adsk.core.Application.get()
ui = app.userInterface
design = app.activeProduct
root_comp = design.rootComponent

# TODO *** Specify the command identity information. ***
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_isogrid_cmd'
CMD_NAME = 'IsoGrid Generator'
CMD_Description = 'Generate an IsoGrid structure'

# Specify that the command will be promoted to the panel.
IS_PROMOTED = True

# TODO *** Define the location where the command button will be created. ***
WORKSPACE_ID = 'FusionSolidEnvironment'
PANEL_ID = 'SolidScriptsAddinsPanel'
COMMAND_BESIDE_ID = 'ScriptsManagerCommand'

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []

# Executed when add-in is run.
def start():
    # Create a command Definition.
    cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)

    # Define an event handler for the command created event. It will be called when the button is clicked.
    futil.add_handler(cmd_def.commandCreated, command_created)

    # ******** Add a button into the UI so the user can run the command. ********
    # Get the target workspace the button will be created in.
    workspace = ui.workspaces.itemById(WORKSPACE_ID)

    # Get the panel the button will be created in.
    panel = workspace.toolbarPanels.itemById(PANEL_ID)

    # Create the button command control in the UI after the specified existing command.
    control = panel.controls.addCommand(cmd_def, COMMAND_BESIDE_ID, False)

    # Specify if the command is promoted to the main toolbar. 
    control.isPromoted = IS_PROMOTED

# Executed when add-in is stopped.
def stop():
    # Get the various UI elements for this command
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    command_control = panel.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)

    # Delete the button command control
    if command_control:
        command_control.deleteMe()

    # Delete the command definition
    if command_definition:
        command_definition.deleteMe()

def command_created(args: adsk.core.CommandCreatedEventArgs):
    futil.log(f'{CMD_NAME} Command Created Event')

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs

    # Create value input fields for wall thickness, unit length, etc.
    defaultLengthUnits = app.activeProduct.unitsManager.defaultLengthUnits
    inputs.addValueInput('thickness_input', 'Wall Thickness', defaultLengthUnits, adsk.core.ValueInput.createByReal(1.0))
    inputs.addValueInput('size_input', 'Triangle Size', defaultLengthUnits, adsk.core.ValueInput.createByReal(10.0))
    inputs.addValueInput('height_input', 'Grid Height', defaultLengthUnits, adsk.core.ValueInput.createByReal(1.0))
    inputs.addValueInput('hole_size_input', 'Hole Diameter', defaultLengthUnits, adsk.core.ValueInput.createByReal(1.0))
    inputs.addValueInput('fillet_radius_input', 'Fillet Radius', defaultLengthUnits, adsk.core.ValueInput.createByReal(0.5))  # New input for fillet radius

    # Connect to the events that are needed by this command.
    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)

def command_execute(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME} Command Execute Event')

    inputs = args.command.commandInputs
    thickness_input = inputs.itemById('thickness_input').value
    size_input = inputs.itemById('size_input').value
    fillet_radius_input = inputs.itemById('fillet_radius_input').value  # Fillet radius input

    try:
        sketches = root_comp.sketches
        xyPlane = root_comp.xYConstructionPlane
        sketch = sketches.add(xyPlane)

        lines = sketch.sketchCurves.sketchLines
        
        # create points of hex
        p1 = adsk.core.Point3D.create(0, 0, 0)
        p2 = adsk.core.Point3D.create(size_input, 0, 0)
        p3 = adsk.core.Point3D.create(size_input * 3 / 2, size_input * 3 ** .5 / 2, 0)
        p4 = adsk.core.Point3D.create(size_input, size_input * 3 ** .5, 0)
        p5 = adsk.core.Point3D.create(0, size_input * 3 ** .5, 0)
        p6 = adsk.core.Point3D.create(-size_input / 2, size_input * 3 ** .5 / 2, 0)
        
        # create lines of hex
        line1 = lines.addByTwoPoints(p1, p2)
        line2 = lines.addByTwoPoints(p2, p3)
        line3 = lines.addByTwoPoints(p3, p4)
        line4 = lines.addByTwoPoints(p4, p5)
        line5 = lines.addByTwoPoints(p5, p6)
        line6 = lines.addByTwoPoints(p6, p1)

        # Add fillets to the hexagon corners
        arcs = sketch.sketchCurves.sketchArcs
        arcs.addFillet(line1, line1.endSketchPoint.geometry, line2, line2.startSketchPoint.geometry, fillet_radius_input)
        arcs.addFillet(line2, line2.endSketchPoint.geometry, line3, line3.startSketchPoint.geometry, fillet_radius_input)
        arcs.addFillet(line3, line3.endSketchPoint.geometry, line4, line4.startSketchPoint.geometry, fillet_radius_input)
        arcs.addFillet(line4, line4.endSketchPoint.geometry, line5, line5.startSketchPoint.geometry, fillet_radius_input)
        arcs.addFillet(line5, line5.endSketchPoint.geometry, line6, line6.startSketchPoint.geometry, fillet_radius_input)
        arcs.addFillet(line6, line6.endSketchPoint.geometry, line1, line1.startSketchPoint.geometry, fillet_radius_input)

        # Get the profile defined by the hexagon and its offset
        prof = sketch.profiles.item(0)

        # Create an extrusion input
        extrudes = root_comp.features.extrudeFeatures
        ext_input = extrudes.createInput(prof, adsk.fusion.FeatureOperations.CutFeatureOperation)

        # Define the extent of the extrusion
        distance = adsk.core.ValueInput.createByReal(thickness_input)
        ext_input.setDistanceExtent(False, distance)

        # Create the extrusion
        extrude = extrudes.add(ext_input)

        ui.messageBox(f'Created')

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))





# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME} Command Destroy Event')
    global local_handlers
    local_handlers = []

