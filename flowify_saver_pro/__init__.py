# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 3
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

bl_info = {
    "name": "Flowify Saver Pro",
    "author": "BERG",
    "version": (0, 9, 0),
    "blender": (4, 3, 0),
    "location": "View3D > Header > Flowify Icon, View3D > N-Panel > Flowify",
    "description": "Auto-save and backup tool for Blender with versioned or timestamped backups and recent file access.",
    "warning": "",
    "category": "System",
    "type": "Add-on",
    "tagline": "Auto-save and manage Blender files with ease",
    "license": ["SPDX:GPL-3.0-or-later"]
}

import bpy
import datetime
import sqlite3
from pathlib import Path
import os
import re
import platform
import gpu
import blf
import bgl
from gpu_extras.batch import batch_for_shader
import math
from bpy.app.handlers import persistent

# --- Notification System ---
class NotificationManager:
    def __init__(self):
        self.message = ""
        self.title = "Flowify Saver Pro"
        self.icon = "INFO"
        self.opacity = 0.0
        self.start_time = 0.0
        self.duration = 3.0  # Seconds to display
        self.fade_duration = 0.5  # Seconds for fade in/out
        self.draw_handler = None
        self.timer = None

    def show(self, message, title="Flowify Saver Pro", icon="INFO"):
        """Schedule a new notification."""
        if self.is_active():
            self.hide()

        self.message = message
        self.title = title
        self.icon = icon
        self.opacity = 0.0
        self.start_time = bpy.context.scene.frame_current / bpy.context.scene.render.fps
        if not bpy.app.timers.is_registered(self.update):
            self.timer = bpy.app.timers.register(self.update, persistent=True)
        self.draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            self.draw_notification, (bpy.context,), 'WINDOW', 'POST_PIXEL'
        )

    def is_active(self):
        """Check if a notification is currently displayed."""
        return self.draw_handler is not None

    def hide(self):
        """Remove the current notification."""
        if self.draw_handler:
            bpy.types.SpaceView3D.draw_handler_remove(self.draw_handler, 'WINDOW')
            self.draw_handler = None
        if self.timer and bpy.app.timers.is_registered(self.update):
            bpy.app.timers.unregister(self.update)
            self.timer = None

    def update(self):
        """Update notification opacity and handle dismissal."""
        current_time = bpy.context.scene.frame_current / bpy.context.scene.render.fps
        elapsed = current_time - self.start_time

        if elapsed < self.fade_duration:
            self.opacity = elapsed / self.fade_duration
        elif elapsed < self.duration - self.fade_duration:
            self.opacity = 1.0
        elif elapsed < self.duration:
            self.opacity = (self.duration - elapsed) / self.fade_duration
        else:
            self.hide()
            return None

        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return 0.01

    def draw_notification(self, context):
        """Draw the notification in the 3D View."""
        try:
            region = context.region
            width = region.width
            height = region.height
            padding = 10
            margin = 20
            max_width = 300
            font_id = 0
            text_size = 12
            title_size = 14

            blf.size(font_id, text_size)
            message_width = blf.dimensions(font_id, self.message)[0]
            blf.size(font_id, title_size)
            title_width = blf.dimensions(font_id, self.title)[0]
            content_width = max(message_width, title_width)
            box_width = min(max(content_width + padding * 2 + 30, 200), max_width)
            box_height = 60
            x = width - box_width - margin
            y = height - box_height - margin

            bg_color = (0.1, 0.1, 0.1, 0.8 * self.opacity)
            border_color = (0.3, 0.3, 0.3, 1.0 * self.opacity)
            text_color = (1.0, 1.0, 1.0, 1.0 * self.opacity)
            icon_colors = {
                'INFO': (0.0, 0.5, 1.0, 1.0 * self.opacity),
                'WARNING': (1.0, 0.7, 0.0, 1.0 * self.opacity),
                'ERROR': (1.0, 0.0, 0.0, 1.0 * self.opacity)
            }
            icon_color = icon_colors.get(self.icon, icon_colors['INFO'])

            bgl.glEnable(bgl.GL_BLEND)
            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            radius = 8
            segments = 16
            vertices = []
            indices = []

            for corner in [(0, 0), (0, 1), (1, 1), (1, 0)]:
                cx = x + (box_width if corner[0] else 0)
                cy = y + (box_height if corner[1] else 0)
                for i in range(segments + 1):
                    angle = math.pi / 2 * corner[0] + (math.pi / 2) * (1 - corner[1]) + (i / segments) * (math.pi / 2)
                    dx = radius * math.cos(angle) * (-1 if corner[0] else 1)
                    dy = radius * math.sin(angle) * (-1 if corner[1] else 1)
                    vertices.append((cx + dx, cy + dy))

            vertices.extend([
                (x + radius, y + radius),
                (x + box_width - radius, y + radius),
                (x + box_width - radius, y + box_height - radius),
                (x + radius, y + box_height - radius)
            ])

            center_idx = len(vertices) - 4
            for i in range(4):
                for j in range(segments):
                    idx = i * (segments + 1) + j
                    next_idx = idx + 1 if j < segments else i * (segments + 1)
                    indices.extend([(center_idx + i, idx, next_idx)])
                if i < 3:
                    indices.append((center_idx + i, center_idx + i + 1, (i + 1) * (segments + 1)))

            batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)
            shader.bind()
            shader.uniform_float("color", bg_color)
            batch.draw(shader)

            bgl.glLineWidth(1)
            vertices_border = [
                (x, y), (x + box_width, y),
                (x + box_width, y + box_height), (x, y + box_height), (x, y)
            ]
            batch_border = batch_for_shader(shader, 'LINE_STRIP', {"pos": vertices_border})
            shader.uniform_float("color", border_color)
            batch_border.draw(shader)

            icon_size = 16
            icon_x = x + padding
            icon_y = y + box_height / 2
            segments = 32
            icon_vertices = [(icon_x, icon_y)]
            for i in range(segments + 1):
                angle = 2 * math.pi * i / segments
                icon_vertices.append((icon_x + icon_size / 2 * math.cos(angle), icon_y + icon_size / 2 * math.sin(angle)))
            icon_indices = [(0, i + 1, i + 2) for i in range(segments)]
            icon_indices[-1] = (0, segments + 1, 1)
            batch_icon = batch_for_shader(shader, 'TRIS', {"pos": icon_vertices}, indices=icon_indices)
            shader.uniform_float("color", icon_color)
            batch_icon.draw(shader)

            blf.size(font_id, title_size)
            blf.color(font_id, *text_color)
            blf.position(font_id, x + padding + 30, y + box_height - padding - 20, 0)
            blf.draw(font_id, self.title)

            blf.size(font_id, text_size)
            blf.position(font_id, x + padding + 30, y + box_height - padding - 40, 0)
            blf.draw(font_id, self.message)

            bgl.glDisable(bgl.GL_BLEND)
            bgl.glLineWidth(1)
        except Exception:
            self.hide()

# Global notification manager
notification_manager = NotificationManager()

def show_notification(message, title="Flowify Saver Pro", icon="INFO"):
    """Display a notification in the 3D View."""
    notification_manager.show(message, title, icon)

# --- Utility Functions ---
def get_recent_files():
    """Retrieve recent .blend files from recent-files.txt."""
    config_dir = Path(bpy.utils.user_resource('CONFIG'))
    recent_file_path = config_dir / "recent-files.txt"
    if not recent_file_path.exists():
        return []
    
    recent_files = []
    with recent_file_path.open('r', encoding='utf-8') as f:
        for line in f:
            file_path = line.strip()
            if file_path and Path(file_path).suffix.lower() == '.blend':
                recent_files.append(file_path)
    return recent_files

# --- Property Definitions ---
def backup_pattern_update(self, context):
    """Callback for backup_pattern changes."""
    pass

class FlowifyProperties(bpy.types.PropertyGroup):
    auto_save_enabled: bpy.props.BoolProperty(
        name="Enable Auto-Save",
        default=False
    )
    auto_save_interval: bpy.props.IntProperty(
        name="Interval (minutes)",
        default=5,
        min=1
    )
    auto_save_mode: bpy.props.EnumProperty(
        name="Auto-save Mode",
        description="Choose how auto-saves are stored: overwrite or create new file",
        items=[
            ('OVERWRITE', "Overwrite", "Overwrite the current file"),
            ('SUFFIX', "Suffix", "Save with an incrementing suffix or timestamp")
        ],
        default='SUFFIX'
    )
    backup_pattern: bpy.props.EnumProperty(
        name="Backup Pattern",
        description="Naming pattern for backups",
        items=[
            ('VERSIONED', "Versioned (e.g., _v001)", "Use incrementing version numbers"),
            ('TIMESTAMPED', "Timestamped (e.g., _backup_DDMMYYYY_HH-MM-SS)", "Use date and time")
        ],
        default='VERSIONED',
        update=backup_pattern_update
    )

# --- Database Handler ---
class VersionDatabase:
    _instance = None
    
    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        self.db_path = Path(bpy.utils.extension_path_user('flowify_saver_pro')) / 'flowify_versions.db'
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self._create_tables()
    
    def _create_tables(self):
        self.conn.execute('DROP TABLE IF EXISTS versions')
        self.conn.execute('''CREATE TABLE versions (
            id INTEGER PRIMARY KEY,
            filepath TEXT UNIQUE,
            timestamp DATETIME,
            base_name TEXT
        )''')
        self.conn.commit()
    
    def add_version(self, filepath):
        base_name = Path(filepath).stem
        timestamp = datetime.datetime.now().isoformat()
        try:
            self.conn.execute('''INSERT INTO versions 
                (filepath, timestamp, base_name)
                VALUES (?, ?, ?)''',
                (str(filepath), timestamp, base_name)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def get_versions(self):
        cursor = self.conn.execute('''SELECT filepath, timestamp 
                                   FROM versions ORDER BY timestamp DESC''')
        return cursor.fetchall()

# --- Core Functionality ---
class FlowifyCore:
    @staticmethod
    def safe_save(filepath, overwrite=False):
        filepath = Path(filepath)
        if not filepath.parent.exists():
            return False
        if not os.access(filepath.parent, os.W_OK):
            return False
        
        if overwrite:
            bpy.ops.wm.save_mainfile(filepath=str(filepath))
        else:
            bpy.ops.wm.save_as_mainfile(filepath=str(filepath), copy=True)
        return True

    @classmethod
    def create_backup(cls, context):
        if not bpy.data.is_saved or not bpy.data.filepath:
            show_notification("Cannot create backup: File is not saved", icon='WARNING')
            return None
        
        original_path = Path(bpy.data.filepath)
        props = context.scene.flowify_props
        save_mode = props.auto_save_mode
        
        if not original_path.parent.exists() or not os.access(original_path.parent, os.W_OK):
            show_notification(f"No write permission for directory", icon='ERROR')
            return None
        
        if save_mode == 'OVERWRITE':
            backup_path = original_path
            if cls.safe_save(backup_path, overwrite=True):
                return backup_path
            return None
        else:
            suffix, base_name = cls._get_suffix(context, original_path, original_path.parent)
            backup_path = original_path.parent / f"{base_name}{suffix}{original_path.suffix}"
            if cls.safe_save(backup_path):
                if VersionDatabase().add_version(backup_path):
                    return backup_path
            return None

    @staticmethod
    def _get_suffix(context, original_path, directory):
        props = context.scene.flowify_props
        base_name = original_path.stem
        
        if props.backup_pattern == 'VERSIONED':
            version_pattern = r'_v(\d{3})$'
            version_match = re.search(version_pattern, base_name)
            if version_match:
                current_version = int(version_match.group(1))
                base_name = base_name[:version_match.start()]
            else:
                current_version = 0
            
            max_num = current_version
            for file in directory.glob(f"{base_name}_v*.blend"):
                match = re.search(version_pattern, file.stem)
                if match:
                    num = int(match.group(1))
                    max_num = max(max_num, num)
            
            suffix = f"_v{max_num + 1:03d}"
            return suffix, base_name
        else:
            timestamp_pattern = r'_backup_\d{8}_\d{2}-\d{2}-\d{2}(?:_\d{3})?$'
            timestamp_match = re.search(timestamp_pattern, base_name)
            if timestamp_match:
                base_name = base_name[:timestamp_match.start()]
            
            timestamp = datetime.datetime.now().strftime("_backup_%d%m%Y_%H-%M-%S")
            counter = 1
            backup_path = directory / f"{base_name}{timestamp}.blend"
            while backup_path.exists():
                backup_path = directory / f"{base_name}{timestamp}_{counter:03d}.blend"
                counter += 1
            suffix = timestamp if counter == 1 else f"{timestamp}_{counter - 1:03d}"
            return suffix, base_name

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
        self.report({'INFO'}, f"Opened: {filepath.name}")
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

# --- UI Components ---
def draw_flowify_icon(self, context):
    layout = self.layout
    props = context.scene.flowify_props
    icon = 'RADIOBUT_ON' if props.auto_save_enabled else 'RADIOBUT_OFF'
    layout.popover(panel="FLOWIFY_PT_POPOVER_PANEL", icon=icon, text="")

class FLOWIFY_PT_PopoverPanel(bpy.types.Panel):
    bl_label = "Flowify Pro"
    bl_idname = "FLOWIFY_PT_POPOVER_PANEL"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'HEADER'
    bl_ui_units_x = 20

    def draw(self, context):
        layout = self.layout
        props = context.scene.flowify_props
        
        box = layout.box()
        box.label(text="Flowify Pro", icon='TOOL_SETTINGS')
        
        box.operator("wm.flowify_save_project", icon='FILE_TICK')
        box.operator("wm.flowify_create_backup", icon='FILE_BACKUP')
        box.operator("wm.flowify_open_project", icon='FILE')
        box.operator("wm.flowify_open_backup_folder", icon='FILE_FOLDER')
        box.operator("wm.flowify_open_recent_project", icon='FILE_REFRESH')
        
        box.separator(factor=0.5)
        
        layout.use_property_split = True
        layout.use_property_decorate = False
        col = box.column(align=True)
        col.prop(props, "auto_save_enabled", icon='CHECKBOX_HLT' if props.auto_save_enabled else 'CHECKBOX_DEHLT')
        box.separator(factor=0.7)
        box.prop(props, "auto_save_mode", icon='FILE_CACHE')
        box.separator(factor=0.7)
        box.prop(props, "auto_save_interval", icon='TIME')
        box.separator(factor=0.7)
        box.prop(props, "backup_pattern", icon='OUTLINER_DATA_GP_LAYER')

class FLOWIFY_PT_NPanel(bpy.types.Panel):
    bl_label = "Flowify Pro"
    bl_idname = "FLOWIFY_PT_NPANEL"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Flowify"

    def draw(self, context):
        layout = self.layout
        props = context.scene.flowify_props
        
        box = layout.box()
        box.label(text="Flowify Pro", icon='TOOL_SETTINGS')
        
        box.operator("wm.flowify_save_project", icon='FILE_TICK')
        box.operator("wm.flowify_create_backup", icon='FILE_BACKUP')
        box.operator("wm.flowify_open_project", icon='FILE')
        box.operator("wm.flowify_open_backup_folder", icon='FILE_FOLDER')
        box.operator("wm.flowify_open_recent_project", icon='FILE_REFRESH')
        
        box.separator(factor=0.5)
        
        layout.use_property_split = True
        layout.use_property_decorate = False
        col = box.column(align=True)
        col.prop(props, "auto_save_enabled", icon='CHECKBOX_HLT' if props.auto_save_enabled else 'CHECKBOX_DEHLT')
        box.separator(factor=0.7)
        box.prop(props, "auto_save_mode", icon='FILE_CACHE')
        box.separator(factor=0.7)
        box.prop(props, "auto_save_interval", icon='TIME')
        box.separator(factor=0.7)
        box.prop(props, "backup_pattern", icon='OUTLINER_DATA_GP_LAYER')

# --- Auto-save System ---
def autosave_timer():
    if not bpy.data.is_saved or not bpy.data.filepath:
        show_notification("Cannot auto-save: File is not saved", icon='WARNING')
        return 60
    if bpy.context.scene.flowify_props.auto_save_enabled:
        bpy.ops.wm.flowify_auto_save()
    return bpy.context.scene.flowify_props.auto_save_interval * 60

# --- Registration ---
def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.flowify_props = bpy.props.PointerProperty(type=FlowifyProperties)
    bpy.app.timers.register(autosave_timer, persistent=True)
    bpy.types.VIEW3D_HT_tool_header.prepend(draw_flowify_icon)

def unregister():
    notification_manager.hide()
    bpy.types.VIEW3D_HT_tool_header.remove(draw_flowify_icon)
    if bpy.app.timers.is_registered(autosave_timer):
        bpy.app.timers.unregister(autosave_timer)
    if hasattr(bpy.types.Scene, 'flowify_props'):
        del bpy.types.Scene.flowify_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

classes = (
    FlowifyProperties,
    WM_OT_FlowifySaveProject,
    WM_OT_FlowifyCreateBackup,
    WM_OT_FlowifyOpenProject,
    WM_OT_FlowifyOpenBackupFolder,
    WM_OT_FlowifyOpenRecentProject,
    WM_OT_FlowifyAutoSave,
    FLOWIFY_PT_PopoverPanel,
    FLOWIFY_PT_NPanel,
)

if __name__ == "__main__":
    register()

