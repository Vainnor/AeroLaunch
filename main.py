import sys
import os
import subprocess
import json
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QPushButton, QListWidget, QListWidgetItem,
    QLabel, QMessageBox, QFileDialog, QInputDialog,
    QDialog, QLineEdit, QFormLayout, QDialogButtonBox
)
from PySide6.QtCore import Qt, Signal, QSettings

winreg = None
if sys.platform == "win32":
    try:
        import winreg
    except ImportError:
        print("Warning: 'winreg' module not available. Registry discovery will be skipped.")

def get_config_file_path():
    app_name = "AeroLaunch"
    org_name = "vainnor"
    settings = QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, org_name, app_name)
    config_dir = os.path.dirname(settings.fileName())
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "config.json")

CONFIG_FILE = get_config_file_path()
print(f"Configuration will be saved/loaded at: {CONFIG_FILE}")

class FlightApp:
    def __init__(self, name, path=None, default_checked=False):
        self.name = name
        self.path = path
        self.default_checked = default_checked

    def to_dict(self):
        return {
            "name": self.name,
            "path": self.path,
            "default_checked": self.default_checked # Include checked state
        }

    @staticmethod
    def from_dict(data):
        return FlightApp(
            data.get("name"),
            data.get("path"),
            data.get("default_checked", False)
        )

class EditApplicationDialog(QDialog):
    def __init__(self, app_name="", app_path="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Application Details")
        self.setGeometry(200, 200, 400, 150)

        self.name_input = QLineEdit(app_name)
        self.path_input = QLineEdit(app_path)
        self.browse_button = QPushButton("Browse...")

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.browse_button.clicked.connect(self._browse_for_path)

        form_layout = QFormLayout()
        form_layout.addRow("Name:", self.name_input)

        path_layout = QHBoxLayout()
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.browse_button)
        form_layout.addRow("Path:", path_layout)

        main_layout = QVBoxLayout()
        main_layout.addLayout(form_layout)
        main_layout.addWidget(self.button_box)
        self.setLayout(main_layout)

    def _browse_for_path(self):
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("Select Application Executable/Bundle")

        if sys.platform == "darwin":
            file_dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
            file_dialog.setNameFilter("Applications (*.app);;All Files (*)")
            file_dialog.setFileMode(QFileDialog.FileMode.Directory)
            file_dialog.setDirectory("/Applications")
        elif sys.platform == "win32":
            file_dialog.setNameFilter("Executables (*.exe);;All Files (*)")
            file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        else:
            file_dialog.setNameFilter("Executables (*);;All Files (*)")
            file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)

        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self.path_input.setText(selected_files[0])

    def get_details(self):
        return self.name_input.text(), self.path_input.text()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AeroLauncher")
        self.setGeometry(100, 100, 600, 400)

        self.available_apps = [
            FlightApp("Microsoft Flight Simulator", default_checked=True),
            FlightApp("Elevatex"),
            FlightApp("Navigraph Charts"),
        ]

        self._load_config()

        self._create_widgets()
        self._create_layout()
        self._connect_signals()
        self._update_app_list_widget()
        self._update_action_buttons_state()

    def _load_config(self):
        if not os.path.exists(CONFIG_FILE):
            print("Config file not found. Using default applications.")
            self._save_config()
            return

        try:
            with open(CONFIG_FILE, 'r') as f:
                config_data = json.load(f)

            current_platform = sys.platform
            apps_data = config_data.get(current_platform, [])

            if apps_data:
                self.available_apps = [FlightApp.from_dict(app_dict) for app_dict in apps_data]
                print(f"Loaded {len(self.available_apps)} applications from config for {current_platform}.")
            else:
                print(f"No specific apps found for {current_platform} in config. Using defaults.")
                self._save_config()

        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "Config Error", f"Error reading config file: {e}\nUsing default applications.")
            print(f"Error reading config file: {e}. Using default applications.")
            # Reset to defaults if config is corrupted
            self.available_apps = [
                FlightApp("Microsoft Flight Simulator", default_checked=True),
                FlightApp("ElevateX"),
                FlightApp("Navigraph Charts"),
            ]
            self._save_config()
        except Exception as e:
            QMessageBox.critical(self, "Config Error", f"An unexpected error occurred loading config: {e}\nUsing default applications.")
            print(f"Unexpected error loading config: {e}. Using default applications.")
            # Reset to defaults on unexpected error
            self.available_apps = [
                FlightApp("Microsoft Flight Simulator", default_checked=True),
                FlightApp("ElevateX"),
                FlightApp("Navigraph Charts"),
            ]
            self._save_config()

    def _save_config(self):
        try:
            apps_for_platform = [app.to_dict() for app in self.available_apps]
            existing_config = {}
            if os.path.exists(CONFIG_FILE):
                try:
                    with open(CONFIG_FILE, 'r') as f:
                        existing_config = json.load(f)
                except json.JSONDecodeError:
                    print("Existing config file is invalid JSON. Overwriting.")
                    existing_config = {}

            current_platform = sys.platform
            existing_config[current_platform] = apps_for_platform

            with open(CONFIG_FILE, 'w') as f:
                json.dump(existing_config, f, indent=4)
            print(f"Saved {len(self.available_apps)} applications to config for {current_platform}.")
        except Exception as e:
            QMessageBox.critical(self, "Config Save Error", f"Error saving config file: {e}")
            print(f"Error saving config file: {e}")

    def _create_widgets(self):
        self.app_list_widget = QListWidget()
        self.app_list_widget.setSelectionMode(QListWidget.SingleSelection)

        self.launch_button = QPushButton("Launch Selected Applications")
        self.auto_discover_button = QPushButton("Auto-Discover Applications")
        self.add_custom_app_button = QPushButton("Add Custom Application...")
        self.edit_app_button = QPushButton("Edit Selected Application")
        self.delete_app_button = QPushButton("Delete Selected Application")

        self.edit_app_button.setEnabled(False)
        self.delete_app_button.setEnabled(False)


    def _create_layout(self):
        main_layout = QVBoxLayout()

        app_selection_label = QLabel("Select Applications to Launch:")
        main_layout.addWidget(app_selection_label)
        main_layout.addWidget(self.app_list_widget)

        button_layout_top = QHBoxLayout()
        button_layout_top.addWidget(self.auto_discover_button)
        button_layout_top.addWidget(self.add_custom_app_button)
        button_layout_top.addStretch()
        button_layout_top.addWidget(self.edit_app_button)
        button_layout_top.addWidget(self.delete_app_button)

        main_layout.addLayout(button_layout_top)

        button_layout_bottom = QHBoxLayout()
        button_layout_bottom.addStretch()
        button_layout_bottom.addWidget(self.launch_button)

        main_layout.addLayout(button_layout_bottom)

        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def _connect_signals(self):
        self.launch_button.clicked.connect(self._launch_selected_applications)
        self.auto_discover_button.clicked.connect(self._auto_discover_applications)
        self.add_custom_app_button.clicked.connect(self._add_custom_application)
        self.edit_app_button.clicked.connect(self._edit_selected_application)
        self.delete_app_button.clicked.connect(self._delete_selected_application)
        self.app_list_widget.itemSelectionChanged.connect(self._update_action_buttons_state)
        # Connect to itemChanged signal to detect checkbox state changes
        self.app_list_widget.itemChanged.connect(self._handle_item_checked_changed)

    def _update_action_buttons_state(self):
        has_selection = bool(self.app_list_widget.selectedItems())
        self.edit_app_button.setEnabled(has_selection)
        self.delete_app_button.setEnabled(has_selection)

    def _handle_item_checked_changed(self, item):
        """Updates the FlightApp object's default_checked state when a checkbox is changed."""
        app = item.data(Qt.UserRole)
        app.default_checked = (item.checkState() == Qt.Checked)
        self._save_config() # Save config immediately after a checkbox state change

    def _update_app_list_widget(self):
        self.app_list_widget.clear()
        for app in self.available_apps:
            item_text = app.name
            if app.path:
                if sys.platform == "darwin" and app.path.endswith(".app"):
                    item_text += f" (Found: {os.path.basename(app.path)})"
                else:
                    item_text += f" (Found: {os.path.basename(app.path)})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, app)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            item.setCheckState(Qt.Checked if app.default_checked else Qt.Unchecked)
            self.app_list_widget.addItem(item)

    def _launch_selected_applications(self):
        launched_count = 0
        # Iterate through all items to ensure all current checked states are saved
        # This is somewhat redundant with _handle_item_checked_changed,
        # but provides a fallback if for some reason that signal isn't caught.
        # It's also necessary to save *before* launching if the user is
        # relying on the launch button to implicitly save state.
        for i in range(self.app_list_widget.count()):
            item = self.app_list_widget.item(i)
            app = item.data(Qt.UserRole)
            app.default_checked = (item.checkState() == Qt.Checked) # Update state before checking

            if item.checkState() == Qt.Checked:
                if app.path and os.path.exists(app.path):
                    print(f"Launching: {app.name} from {app.path}")
                    try:
                        if sys.platform == "darwin":
                            subprocess.Popen(["open", "-a", app.path])
                        elif sys.platform == "win32":
                            subprocess.Popen(app.path, shell=True)
                        else:
                            subprocess.Popen([app.path])
                        launched_count += 1
                    except Exception as e:
                        print(f"Error launching {app.name}: {e}")
                        QMessageBox.warning(self, "Launch Error",
                                            f"Could not launch {app.name}:\n{e}")
                else:
                    QMessageBox.warning(self, "Missing Path",
                                        f"Cannot launch '{app.name}'. Path is not set or file not found.")

        self._save_config() # Save config after launching (to persist final checked states)

        if launched_count > 0:
            QMessageBox.information(self, "Launch Complete",
                                    f"Attempted to launch {launched_count} application(s).")
        else:
            QMessageBox.information(self, "Launch", "No applications selected or ready to launch.")

    def _auto_discover_applications(self):
        QMessageBox.information(self, "Discovering", "Starting auto-discovery. This may take a moment...")
        print("Starting auto-discovery...")

        found_count = 0
        for app_obj in self.available_apps:
            original_path = app_obj.path
            new_path = self._find_app_path(app_obj.name)

            if new_path and new_path != original_path:
                app_obj.path = new_path
                found_count += 1
                print(f"Found {app_obj.name} at: {new_path}")
            elif not app_obj.path and new_path:
                 app_obj.path = new_path
                 found_count += 1
                 print(f"Found {app_obj.name} at: {new_path}")

        self._update_app_list_widget()
        self._save_config()

        if found_count > 0:
            QMessageBox.information(self, "Discovery Complete",
                                    f"Auto-discovery found {found_count} new application paths.")
        else:
            QMessageBox.information(self, "Discovery Complete",
                                    "No new application paths were found or updated.")

    def _add_custom_application(self):
        app_name, ok = QInputDialog.getText(self, "Add Custom Application", "Enter Application Name:")

        if ok and app_name:
            if any(app.name.lower() == app_name.lower() for app in self.available_apps):
                QMessageBox.warning(self, "Duplicate Name", f"An application named '{app_name}' already exists (case-insensitive). Please choose a different name.")
                return

            edit_dialog = EditApplicationDialog(app_name=app_name, parent=self)
            if edit_dialog.exec() == QDialog.Accepted:
                new_app_name, new_app_path = edit_dialog.get_details()
                if not new_app_path:
                    QMessageBox.warning(self, "Input Error", "Application path cannot be empty.")
                    return

                if new_app_name.lower() != app_name.lower() and \
                   any(app.name.lower() == new_app_name.lower() for app in self.available_apps):
                    QMessageBox.warning(self, "Duplicate Name", f"An application named '{new_app_name}' already exists (case-insensitive). Please choose a different name.")
                    return

                new_app = FlightApp(new_app_name, path=new_app_path)
                self.available_apps.append(new_app)
                self._update_app_list_widget()
                self._save_config()
                QMessageBox.information(self, "App Added", f"'{new_app_name}' added successfully!")
            else:
                QMessageBox.information(self, "Cancelled", "Adding custom application cancelled.")
        elif ok and not app_name:
            QMessageBox.warning(self, "Input Error", "Application name cannot be empty.")
        else:
            QMessageBox.information(self, "Cancelled", "Adding custom application cancelled.")

    def _edit_selected_application(self):
        selected_items = self.app_list_widget.selectedItems()
        if not selected_items:
            return

        selected_item = selected_items[0]
        app_to_edit = selected_item.data(Qt.UserRole)

        edit_dialog = EditApplicationDialog(
            app_name=app_to_edit.name,
            app_path=app_to_edit.path if app_to_edit.path else "",
            parent=self
        )

        if edit_dialog.exec() == QDialog.Accepted:
            new_name, new_path = edit_dialog.get_details()

            if not new_name:
                QMessageBox.warning(self, "Input Error", "Application name cannot be empty.")
                return
            if not new_path:
                QMessageBox.warning(self, "Input Error", "Application path cannot be empty.")
                return

            if new_name.lower() != app_to_edit.name.lower() and \
               any(app.name.lower() == new_name.lower() for app in self.available_apps if app != app_to_edit):
                QMessageBox.warning(self, "Duplicate Name", f"An application named '{new_name}' already exists (case-insensitive). Please choose a different name.")
                return

            app_to_edit.name = new_name
            app_to_edit.path = new_path

            self._update_app_list_widget()
            self._save_config()
            QMessageBox.information(self, "Edit Complete", f"Application '{new_name}' updated successfully!")
        else:
            QMessageBox.information(self, "Cancelled", "Editing application cancelled.")

    def _delete_selected_application(self):
        selected_items = self.app_list_widget.selectedItems()
        if not selected_items:
            return

        selected_item = selected_items[0]
        app_to_delete = selected_item.data(Qt.UserRole)

        reply = QMessageBox.question(self, "Confirm Delete",
                                     f"Are you sure you want to delete '{app_to_delete.name}'?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.available_apps.remove(app_to_delete)
            self._update_app_list_widget()
            self._save_config()
            QMessageBox.information(self, "Delete Complete", f"Application '{app_to_delete.name}' deleted.")
        else:
            QMessageBox.information(self, "Cancelled", "Delete operation cancelled.")

    def _find_app_path(self, app_name):
        if sys.platform == "win32":
            app_info = {
                "Microsoft Flight Simulator": {
                    "exe": "FlightSimulator.exe",
                    "subdirs": [
                        os.path.join("Steam", "steamapps", "common", "MicrosoftFlightSimulator"),
                        os.path.join("WpSystem", "Microsoft.FlightSimulator_8wekyb3d8bbwe", "LocalCache", "Packages", "Microsoft.FlightSimulator_8wekyb3d8bbwe")
                    ],
                    "registry_key": r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 1250410"
                },
                "ElevateX": {
                    "exe": "Elevatex.exe",
                    "subdirs": ["Elevatex", "ElevateX Beta"]
                },
                "Navigraph Charts": {
                    "exe": "Navigraph Charts.exe",
                    "subdirs": ["Navigraph", "Navigraph Charts"],
                    "registry_key": r"SOFTWARE\Navigraph\Charts"
                },
            }

            info = app_info.get(app_name)
            if not info:
                print(f"No auto-discovery info for: {app_name} on Windows. Skipping auto-discovery for this app.")
                return None

            exe_name = info["exe"]
            potential_subdirs = info.get("subdirs", [])
            registry_key = info.get("registry_key")

            program_files_paths = [
                os.environ.get("ProgramFiles"),
                os.environ.get("ProgramFiles(x86)"),
                os.environ.get("LocalAppData")
            ]
            program_files_paths = [p for p in program_files_paths if p]

            for base_path in program_files_paths:
                for subdir in potential_subdirs:
                    full_path = os.path.join(base_path, subdir, exe_name)
                    if os.path.exists(full_path):
                        print(f"Found {app_name} via file system: {full_path}")
                        return full_path

                direct_path = os.path.join(base_path, app_name, exe_name)
                if os.path.exists(direct_path):
                    print(f"Found {app_name} directly in Program Files: {direct_path}")
                    return direct_path

            if winreg and registry_key:
                try:
                    for hkey_root in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                        try:
                            key = winreg.OpenKey(hkey_root, registry_key, 0, winreg.KEY_READ)
                            try:
                                install_location, _ = winreg.QueryValueEx(key, "InstallLocation")
                                candidate_path = os.path.join(install_location, exe_name)
                                if os.path.exists(candidate_path):
                                    print(f"Found {app_name} via registry (InstallLocation): {candidate_path}")
                                    return candidate_path
                            except FileNotFoundError:
                                pass

                            try:
                                path_val, _ = winreg.QueryValueEx(key, "Path")
                                candidate_path = os.path.join(path_val, exe_name)
                                if os.path.exists(candidate_path):
                                    print(f"Found {app_name} via registry (Path): {candidate_path}")
                                    return candidate_path
                            except FileNotFoundError:
                                pass

                            winreg.CloseKey(key)
                        except FileNotFoundError:
                            continue
                except Exception as e:
                    print(f"Error accessing registry for {app_name}: {e}")

            print(f"Could not find path for {app_name} on Windows.")
            return None

        elif sys.platform == "darwin":
            macos_app_info = {
                "Navigraph Charts": {
                    "bundle_name": "Navigraph Charts.app",
                    "bundle_id": "com.navigraph.charts"
                }
            }

            info = macos_app_info.get(app_name)
            if not info:
                print(f"No auto-discovery info for: {app_name} on macOS. Skipping auto-discovery for this app.")
                return None

            bundle_name = info["bundle_name"]
            bundle_id = info.get("bundle_id")

            system_app_path = os.path.join("/Applications", bundle_name)
            if os.path.exists(system_app_path):
                print(f"Found {app_name} in /Applications: {system_app_path}")
                return system_app_path

            user_app_path = os.path.join(os.path.expanduser("~/Applications"), bundle_name)
            if os.path.exists(user_app_path):
                print(f"Found {app_name} in ~/Applications: {user_app_path}")
                return user_app_path

            if bundle_id:
                try:
                    cmd = ["mdfind", f'kMDItemCFBundleIdentifier == "{bundle_id}"']
                    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    found_paths = result.stdout.strip().split('\n')
                    for path in found_paths:
                        if path and path.endswith(".app") and os.path.exists(path):
                            print(f"Found {app_name} via mdfind (bundle ID): {path}")
                            return path
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    print(f"Error using mdfind for {app_name} (bundle ID {bundle_id}): {e}")

            print(f"Could not find path for {app_name} on macOS.")
            return None
        else:
            print(f"Platform {sys.platform} not fully supported for auto-discovery yet.")
            return None

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())