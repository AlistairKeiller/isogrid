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

    try:
        sketches = root_comp.sketches
        sketch = sketches.add(face_selection)

        lines = sketch.sketchCurves.sketchLines
        
        # Find the minX and minY of every profile in the existing sketch
        min_x = float('inf')
        min_y = float('inf')
        max_x = float('-inf')
        max_y = float('-inf')
        for profile in sketch.profiles:
            for loop in profile.profileLoops:
                for profile_curve in loop.profileCurves:
                    start_point = profile_curve.geometry.startPoint
                    end_point = profile_curve.geometry.endPoint
                    min_x = min(min_x, start_point.x, end_point.x)
                    min_y = min(min_y, start_point.y, end_point.y)
                    max_x = max(max_x, start_point.x, end_point.x)
                    max_y = max(max_y, start_point.y, end_point.y)

        # Use the min_x, min_y, max_x, and max_y as the bounding points
        min_point = adsk.core.Point3D.create(min_x, min_y, 0)
        max_point = adsk.core.Point3D.create(max_x, max_y, 0)

        # Create a honeycomb pattern of hexagons spaced by wall_thickness up to max_point
        current_y = min_point.y
        row_index = 0  # keep track of which row we are in

        while current_y < max_point.y:
            current_x = min_point.x
            
            # Offset every other row to achieve the staggered honeycomb effect
            if row_index % 2 == 1:
                current_x += size_input * 1.5 + thickness_input / 2  # Shift half the width of the hexagon
            
            while current_x < max_point.x:
                # create points of hex starting from the lower left corner of the bounding box
                p1 = adsk.core.Point3D.create(current_x + size_input / 2, current_y, 0)
                p2 = adsk.core.Point3D.create(current_x + size_input * 1.5, current_y, 0)
                p3 = adsk.core.Point3D.create(current_x + size_input * 2, current_y + size_input * 3 ** 0.5 / 2, 0)
                p4 = adsk.core.Point3D.create(current_x + size_input * 1.5, current_y + size_input * 3 ** 0.5, 0)
                p5 = adsk.core.Point3D.create(current_x + size_input / 2, current_y + size_input * 3 ** 0.5, 0)
                p6 = adsk.core.Point3D.create(current_x, current_y + size_input * 3 ** 0.5 / 2, 0)

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

                # Move to the next hexagon position
                current_x += size_input * 3 + thickness_input  # Adjust spacing between hexagons

            # Move to the next row of hexagons
            current_y += size_input * 3 ** 0.5 / 2 + thickness_input  # Adjust vertical spacing
            row_index += 1  # Increase the row index



        hex_area = (3 * (3 ** 0.5) * (size_input ** 2)) / 2
        prof = max((p for p in sketch.profiles if p.areaProperties().area < hex_area), key=lambda p: p.areaProperties().area)

        # Create an extrusion input
        extrudes = root_comp.features.extrudeFeatures
        ext_input = extrudes.createInput(prof, adsk.fusion.FeatureOperations.CutFeatureOperation)

        # Define the extent of the extrusion to go downwards
        distance = adsk.core.ValueInput.createByReal(-height_input)
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

