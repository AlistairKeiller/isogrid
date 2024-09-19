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

# Function that is called when a user clicks the corresponding button in the UI.
def command_created(args: adsk.core.CommandCreatedEventArgs):
    futil.log(f'{CMD_NAME} Command Created Event')

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs

    # Create value input fields for wall thickness, unit length, etc.
    defaultLengthUnits = app.activeProduct.unitsManager.defaultLengthUnits
    inputs.addValueInput('thickness_input', 'Wall Thickness', defaultLengthUnits, adsk.core.ValueInput.createByReal(0.1))
    inputs.addValueInput('size_input', 'Triangle Size', defaultLengthUnits, adsk.core.ValueInput.createByReal(1.0))
    inputs.addValueInput('height_input', 'Grid Height', defaultLengthUnits, adsk.core.ValueInput.createByReal(10.0))

    # Connect to the events that are needed by this command.
    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)

def command_execute(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME} Command Execute Event')

    # Get the inputs
    inputs = args.command.commandInputs
    thickness_input = inputs.itemById('thickness_input').value
    size_input = inputs.itemById('size_input').value
    height_input = inputs.itemById('height_input').value

    # Create a sketch for the base triangle
    sketches = root_comp.sketches
    xy_plane = root_comp.xYConstructionPlane
    sketch = sketches.add(xy_plane)

    # Create an equilateral triangle in the sketch
    points = [
        adsk.core.Point3D.create(0, 0, 0),
        adsk.core.Point3D.create(size_input, 0, 0),
        adsk.core.Point3D.create(size_input / 2, (size_input * (3 ** 0.5)) / 2, 0)
    ]
    lines = sketch.sketchCurves.sketchLines
    for i in range(len(points)):
        lines.addByTwoPoints(points[i], points[(i + 1) % 3])

    # Extrude the triangle
    prof = sketch.profiles.item(0)
    extrudes = root_comp.features.extrudeFeatures
    ext_input = extrudes.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    distance = adsk.core.ValueInput.createByReal(height_input)
    ext_input.setDistanceExtent(False, distance)
    extrude = extrudes.add(ext_input)

    # Use the shell tool to adjust wall thickness
    shellFeats = root_comp.features.shellFeatures
    shellInput = shellFeats.createInput(extrude.bodies.item(0), False)
    shellThickness = adsk.core.ValueInput.createByReal(thickness_input)
    shellInput.insideThickness = shellThickness
    shellFeats.add(shellInput)

    # Create circular pattern of 6 triangles
    circularPatterns = root_comp.features.circularPatternFeatures
    entities = adsk.core.ObjectCollection.create()
    entities.add(extrude.bodies.item(0))
    z_axis = root_comp.zConstructionAxis
    circularPatternInput = circularPatterns.createInput(entities, z_axis)
    circularPatternInput.quantity = adsk.core.ValueInput.createByReal(6)
    circularPatternInput.totalAngle = adsk.core.ValueInput.createByString('360 deg')
    circularPatterns.add(circularPatternInput)

    # Create a linear pattern for the isogrid
    linearPatterns = root_comp.features.rectangularPatternFeatures
    linearPatternInput = linearPatterns.createInput(entities, root_comp.xConstructionAxis, root_comp.yConstructionAxis)
    linearPatternInput.quantityOne = adsk.core.ValueInput.createByReal(5)  # Adjust as needed
    linearPatternInput.quantityTwo = adsk.core.ValueInput.createByReal(5)  # Adjust as needed
    linearPatterns.add(linearPatternInput)

    # Log and display message
    futil.log(f'{CMD_NAME} Isogrid Generated')
    ui.messageBox(f'Isogrid created with wall thickness {thickness_input} and triangle size {size_input}')

# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME} Command Destroy Event')
    global local_handlers
    local_handlers = []

