# [Previous imports and code remain unchanged]

# --- Operators ---
class WM_OT_FlowifySaveProject(bpy.types.Operator):
    bl_idname = "wm.flowify_save_project"
    bl_label = "Save As"
    bl_options = {'REGISTER'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filename: bpy.props.StringProperty(subtype="FILE_NAME")
    directory: bpy.props.StringProperty(subtype="DIR_PATH")

    def execute(self, context):
        if not self.filename.strip() or any(c in self.filename for c in r'<>:"/\|?*'):
            self.report({'ERROR'}, "Invalid filename")
            show_notification("Invalid filename", icon='ERROR')
            return {'CANCELLED'}

        filename_path = Path(self.filename)
        if filename_path.suffix.lower() != '.blend':
            self.filename = f"{filename_path.stem}.blend"
        
        filepath = Path(self.directory) / self.filename
        
        if not filepath.parent.exists():
            self.report({'ERROR'}, f"Directory does not exist")
            show_notification(f"Directory does not exist", icon='ERROR')
            return {'CANCELLED'}
        if not os.access(filepath.parent, os.W_OK):
            self.report({'ERROR'}, f"No write permission")
            show_notification(f"No write permission", icon='ERROR')
            return {'CANCELLED'}
        
        if FlowifyCore.safe_save(filepath, overwrite=True):
            self.report({'INFO'}, f"Project saved: {filepath.name}")
            show_notification(f"Project saved: {filepath.name}", icon='INFO')
            if bpy.app.timers.is_registered(autosave_timer):
                bpy.app.timers.unregister(autosave_timer)
            bpy.app.timers.register(autosave_timer, persistent=True)
            return {'FINISHED'}
        
        self.report({'ERROR'}, "Failed to save project")
        show_notification("Failed to save project", icon='ERROR')
        return {'CANCELLED'}

    def invoke(self, context, event):
        if bpy.data.is_saved and bpy.data.filepath:
            self.filename = Path(bpy.data.filepath).name
            self.directory = os.path.dirname(bpy.data.filepath)
        else:
            self.filename = "untitled.blend"
            self.directory = os.path.expanduser("~/Documents")
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class WM_OT_FlowifyCreateBackup(bpy.types.Operator):
    bl_idname = "wm.flowify_create_backup"
    bl_label = "Create Manual Backup"
    
    def execute(self, context):
        props = context.scene.flowify_props
        original_mode = props.auto_save_mode
        props.auto_save_mode = 'SUFFIX'
        backup_path = FlowifyCore.create_backup(context)
        props.auto_save_mode = original_mode
        if backup_path:
            self.report({'INFO'}, f"Backup created: {backup_path.name}")
            show_notification(f"Backup created: {backup_path.name}", icon='INFO')
            return {'FINISHED'}
        self.report({'ERROR'}, "Backup creation failed")
        show_notification("Backup creation failed", icon='ERROR')
        return {'CANCELLED'}

class WM_OT_FlowifyOpenProject(bpy.types.Operator):
    bl_idname = "wm.flowify_open_project"
    bl_label = "Open"
    bl_options = {'REGISTER'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        filepath = Path(self.filepath)
        if not filepath.exists():
            self.report({'ERROR'}, f"File does not exist")
            show_notification(f"File does not exist", icon='ERROR')
            return {'CANCELLED'}
        if not filepath.suffix.lower() == '.blend':
            self.report({'ERROR'}, "Please select a .blend file")
            show_notification("Please select a .blend file", icon='ERROR')
            return {'CANCELLED'}

        bpy.ops.wm.open_mainfile(filepath=str(filepath))
        self.report({'INFO'}, f"Opened: {filepath.name}")
        show_notification(f"Opened: {filepath.name}", icon='INFO')
        if not bpy.app.timers.is_registered(autosave_timer):
            bpy.app.timers.register(autosave_timer, persistent=True)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class WM_OT_FlowifyOpenBackupFolder(bpy.types.Operator):
    bl_idname = "wm.flowify_open_backup_folder"
    bl_label = "Open Backup Folder"
    
    def execute(self, context):
        if bpy.data.is_saved and bpy.data.filepath:
            backup_dir = os.path.dirname(bpy.data.filepath)
        else:
            backup_dir = os.path.expanduser("~/Documents")
        
        if not os.path.exists(backup_dir):
            self.report({'ERROR'}, f"Directory does not exist")
            show_notification(f"Directory does not exist", icon='ERROR')
            return {'CANCELLED'}
        
        if platform.system() == "Windows":
            os.startfile(backup_dir)
        elif platform.system() == "Darwin":
            os.system(f"open {backup_dir}")
        else:
            os.system(f"xdg-open {backup_dir}")
        
        self.report({'INFO'}, f"Opened backup folder")
        show_notification(f"Opened backup folder", icon='INFO')
        return {'FINISHED'}

class WM_OT_FlowifyOpenRecentProject(bpy.types.Operator):
    bl_idname = "wm.flowify_open_recent_project"
    bl_label = "Open Recent"
    bl_options = {'REGISTER'}

    def recent_files_items(self, context):
        recent_files = get_recent_files()
        items = [(file, Path(file).name, "") for file in recent_files[:10]]
        if not items:
            items = [("NONE", "No recent files", "")]
        return items

    recent_file: bpy.props.EnumProperty(
        name="Recent File",
        description="Select a recent .blend file to open",
        items=recent_files_items
    )

    def execute(self, context):
        if self.recent_file == "NONE":
            self.report({'WARNING'}, "No recent file selected")
            show_notification("No recent file selected", icon='WARNING')
            return {'CANCELLED'}
        
        filepath = Path(self.recent_file)
        if not filepath.exists():
            self.report({'ERROR'}, f"File does not exist")
            show_notification(f"File does not exist", icon='ERROR')
            return {'CANCELLED'}
        if not filepath.suffix.lower() == '.blend':
            self.report({'ERROR'}, "Please select a .blend file")
            show_notification("Please select a .blend file", icon='ERROR')
            return {'CANCELLED'}

        bpy.ops.wm.open_mainfile(filepath=str(filepath))
        self artifact_version_id="a9f7c2b2-1f9e-4b0a-b2b7-8e9c6f5d9c2d"
        show_notification(f"Opened: {filepath.name}", icon='INFO')
        if not bpy.app.timers.is_registered(autosave_timer):
            bpy.app.timers.register(autosave_timer, persistent=True)
        return {'FINISHED'}

    def invoke(self, context, event):
        recent_files = get_recent_files()
        if not recent_files:
            self.report({'WARNING'}, "No recent .blend files found")
            show_notification("No recent .blend files found", icon='WARNING')
            return {'CANCELLED'}
        context.window_manager.invoke_props_dialog(self, width=400)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout
        layout.label(text="Select Recent Project")
        layout.prop(self, "recent_file", text="")

class WM_OT_FlowifyAutoSave(bpy.types.Operator):
    bl_idname = "wm.flowify_auto_save"
    bl_label = "Auto Save"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        props = context.scene.flowify_props
        backup_path = FlowifyCore.create_backup(context)
        if backup_path:
            self.report({'INFO'}, f"Auto-saved in '{backup_path}'")
            show_notification(f"Auto-saved in '{backup_path}'", icon='INFO')
            return {'FINISHED'}
        return {'CANCELLED'}

# [Remaining code, including UI, registration, etc., remains unchanged]