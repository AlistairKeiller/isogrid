import math
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
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_hexgrid_cmd'
CMD_NAME = 'HexGrid Generator'
CMD_Description = 'Generate an HexGrid structure'

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
    inputs.addValueInput('size_input', 'Hexagon Size', defaultLengthUnits, adsk.core.ValueInput.createByReal(10.0))
    inputs.addValueInput('height_input', 'Extrude Height', defaultLengthUnits, adsk.core.ValueInput.createByReal(1.0))
    inputs.addValueInput('fillet_radius_input', 'Fillet Radius', defaultLengthUnits, adsk.core.ValueInput.createByReal(0.5))  # New input for fillet radius

    # Add a selection input for selecting a face
    selection_input = inputs.addSelectionInput('face_selection', 'Select Face', 'Select a face to place the grid on')
    selection_input.addSelectionFilter(adsk.core.SelectionCommandInput.SolidFaces)
    selection_input.setSelectionLimits(1, 1)

    # Connect to the events that are needed by this command.
    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)

def command_execute(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME} Command Execute Event')

    inputs = args.command.commandInputs
    thickness_input = inputs.itemById('thickness_input').value
    size_input = inputs.itemById('size_input').value
    height_input = inputs.itemById('height_input').value
    fillet_radius_input = inputs.itemById('fillet_radius_input').value  # Fillet radius input

    # Get the selected face
    face_selection = inputs.itemById('face_selection').selection(0).entity
    bounding_box = face_selection.boundingBox
    evaluator = face_selection.evaluator

    try:
        sketches = root_comp.sketches
        sketch = sketches.add(face_selection)
        lines = sketch.sketchCurves.sketchLines
        points = sketch.sketchPoints

        # Find the minX and minY of every profile in the existing sketch
        min_point = sketch.modelToSketchSpace(bounding_box.minPoint)
        max_point = sketch.modelToSketchSpace(bounding_box.maxPoint)
        center_point = adsk.core.Point3D.create((min_point.x + max_point.x) / 2, (min_point.y + max_point.y) / 2, 0)
        
        # gird of points centered at center_point=
        for x in range(math.floor((max_point.x-min_point.x)/size_input)+1):
            for y in range(math.floor((max_point.y-min_point.y)/size_input)+1):
                points.add(adsk.core.Point3D.create(min_point.x+x*size_input+(max_point.x-min_point.x)%size_input/2, min_point.y+y*size_input+(max_point.y-min_point.y)%size_input/2, 0))

        ui.messageBox(f'Created')

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))



# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME} Command Destroy Event')
    global local_handlers
    local_handlers = []

