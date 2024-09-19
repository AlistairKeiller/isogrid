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

# Function that is called when a user clicks the corresponding button in the UI.
def command_created(args: adsk.core.CommandCreatedEventArgs):
    futil.log(f'{CMD_NAME} Command Created Event')

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs

    # Create value input fields for wall thickness, unit length, etc.
    defaultLengthUnits = app.activeProduct.unitsManager.defaultLengthUnits
    inputs.addValueInput('thickness_input', 'Wall Thickness', defaultLengthUnits, adsk.core.ValueInput.createByReal(0.1))
    inputs.addValueInput('size_input', 'Triangle Size', defaultLengthUnits, adsk.core.ValueInput.createByReal(10.0))
    inputs.addValueInput('height_input', 'Grid Height', defaultLengthUnits, adsk.core.ValueInput.createByReal(1.0))

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

    # Log and display message
    futil.log(f'{CMD_NAME} Isogrid Generated')

    # Begin code to create the triangle
    try:
        # Get the root component of the active design
        design = adsk.fusion.Design.cast(app.activeProduct)
        root_comp = design.rootComponent

        # Create a new sketch on the XY plane
        sketches = root_comp.sketches
        xyPlane = root_comp.xYConstructionPlane
        sketch = sketches.add(xyPlane)

        # Draw an equilateral triangle with side length size_input
        lines = sketch.sketchCurves.sketchLines

        # Calculate the points for the triangle
        half_size = size_input / 2.0
        triangle_height = (size_input * (3 ** 0.5)) / 2.0

        p1 = adsk.core.Point3D.create(-half_size, 0, 0)
        p2 = adsk.core.Point3D.create(half_size, 0, 0)
        p3 = adsk.core.Point3D.create(0, triangle_height, 0)

        line1 = lines.addByTwoPoints(p1, p2)
        line2 = lines.addByTwoPoints(p2, p3)
        line3 = lines.addByTwoPoints(p3, p1)

        # Offset the triangle inwards by wall thickness
        entities = adsk.core.ObjectCollection.create()
        entities.add(line1)
        entities.add(line2)
        entities.add(line3)

        # Use a Point3D for the offset direction (center of the triangle)
        point_inside = adsk.core.Point3D.create(0, triangle_height / 3.0, 0)

        offsetCurves = sketch.offset(
            entities,
            point_inside,
            -thickness_input  # Negative to offset inwards
        )

        # Now we have two profiles: the outer and inner triangle
        # We need to get the profile between them
        profs = sketch.profiles

        # Find the profile with two loops (outer and inner)
        prof = None
        for profile in profs:
            if profile.profileLoops.count == 2:
                prof = profile
                break

        if prof is None:
            ui.messageBox('Failed to get the profile for extrusion')
            return

        # Create an extrusion input
        extrudes = root_comp.features.extrudeFeatures
        extInput = extrudes.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)

        # Define the distance extent
        distance = adsk.core.ValueInput.createByReal(height_input)
        extInput.setDistanceExtent(False, distance)

        # Create the extrusion
        extrudes.add(extInput)

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME} Command Destroy Event')
    global local_handlers
    local_handlers = []

