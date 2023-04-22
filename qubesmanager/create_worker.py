#!/usr/bin/python3
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2012  Agnieszka Kostrzewa <agnieszka.kostrzewa@gmail.com>
# Copyright (C) 2012  Marek Marczykowski <marmarek@mimuw.edu.pl>
# Copyright (C) 2017  Wojtek Porczyk <woju@invisiblethingslab.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program; if not, see <http://www.gnu.org/licenses/>.
#
#
import json
import os
import random
import re
import shelve
import string
import sys
import subprocess
import time

from PyQt5.QtCore import QProcess, QObject, pyqtSignal, pyqtSlot
from PyQt5 import QtCore, QtWidgets, QtGui  # pylint: disable=import-error

from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QFont, QBrush, QColor
from PyQt5.QtWidgets import QStyledItemDelegate, QComboBox

import qubesadmin
import qubesadmin.tools
import qubesadmin.exc

from . import utils
from . import bootfromdevice
from . import resources_rc

from .ui_createworker import Ui_NewWorkerDlg  # pylint: disable=import-error

import subprocess


class CustomItemDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super(CustomItemDelegate, self).initStyleOption(option, index)
        value = index.data(Qt.DisplayRole)

        if value == "Windows":
            option.displayAlignment = Qt.AlignCenter
            font = QFont(option.font)
            font.setBold(True)
            option.font = font
            option.backgroundBrush = QBrush(QColor("blue"))

        if value == "Linux templates":
            option.displayAlignment = Qt.AlignCenter
            font = QFont(option.font)
            font.setBold(True)
            option.font = font
            option.backgroundBrush = QBrush(QColor("green"))

        if value == "Unikernels":
            option.displayAlignment = Qt.AlignCenter
            font = QFont(option.font)
            font.setBold(True)
            option.font = font
            option.backgroundBrush = QBrush(QColor("black"))


def get_step(script, run_on_fail):
    return {
        "script": script,
        "run_on_fail": run_on_fail
    }


class FancyManager:
    fancy_directory = os.path.expanduser("~/.qubes-fancy-manager")
    fancy_mount_path = os.path.join(fancy_directory, 'loop_device_backing_file.img')
    fancy_mount_point_path = os.path.join(fancy_directory, 'temp_mount')
    fancy_state_path = os.path.join(fancy_directory, 'state')

    def __init__(self):
        self.run_once_with_flag(self.add_in_options, 'installed_in_options')
        os.makedirs(self.fancy_directory, exist_ok=True)

        unman_signing_key = "/etc/pki/rpm-gpg/RPM-GPG-KEY-unman"

        self.available_installations = [
            ("Linux templates", "separator"),
            # ("qubes.3isec.org templates"),
            ("qubes-template-archlinux-minimal-4.0.6-202301300342",
             "qubes-template-archlinux-minimal-4.0.6-202301300342", "unman", "arch.png"),
            ("qubes-template-blackarch-4.0.6-202302042136", "qubes-template-blackarch-4.0.6-202302042136", "unman",
             "blackarch.png"),
            ("qubes-template-bookworm-minimal-4.0.6-202210290334", "qubes-template-bookworm-minimal-4.0.6-202210290334",
             "unman", "debian.png"),
            ("qubes-template-debian-12-4.0.6-202301242054", "qubes-template-debian-12-4.0.6-202301242054", "unman",
             "debian.png"),
            ("qubes-template-focal-4.0.6-202208271536", "qubes-template-focal-4.0.6-202208271536", "unman",
             "ubuntu.png"),
            ("qubes-template-focal-minimal-4.0.6-202208260823", "qubes-template-focal-minimal-4.0.6-202208260823",
             "unman", "ubuntu.png"),
            ("qubes-template-jammy-4.0.6-202205012228", "qubes-template-jammy-4.0.6-202205012228", "unman",
             "ubuntu.png"),
            ("qubes-template-kali-4.0.6-202302232007", "qubes-template-kali-4.0.6-202302232007", "unman", "kali11.png"),
            ("qubes-template-parrot-pwn-4.0.6-202301281509", "qubes-template-parrot-pwn-4.0.6-202301281509", "unman",
             "parrot.png"),
            ("qubes-template-parrot_full-4.0.6-202210290410", "qubes-template-parrot_full-4.0.6-202210290410", "unman",
             "parrot.png"),
            ("qubes-template-una-4.0.6-202205202253", "qubes-template-una-4.0.6-202205202253", "unman", "mint.png"),
            ("Windows", "separator"),
            ("win10x64-ltsc-eval", "win10x64-ltsc-eval", "windows", "win10x64-ltsc-eval.png"),
            ("Unikernels", "separator"),
            ("mirage-firewall", "mirage-firewall", "mirage", "mirage-firewall.png")
        ]

    def run_once_with_flag(self, f , flag):
        with shelve.open(self.fancy_state_path) as db:
            if flag in db:
                return
            f()
            db[flag] = "yes"

    def add_in_options(self):
        desktop_entry = """[Desktop Entry]
        Version=1.0
        Type=Application
        Name=qubes-fancy-manager
        GenericName=qubes-fancy-manager
        Comment=Description of My Custom Program
        Exec={}
        Icon=qubes-manager
        Terminal=false
        Categories=QubesTools;
        """
        if getattr(sys, 'frozen', False):
            # The application is run as a bundle (created by PyInstaller)
            executable_path = sys.executable
        else:
            # The application is run as a script
            executable_path = os.path.realpath(__file__)

        # Create the desktop entry content
        desktop_entry = desktop_entry.format(executable_path)

        # Create the desktop entry file
        desktop_entry_file = os.path.join(self.fancy_directory, 'qubes-fancy-manager.desktop')

        # Check if the script is running in dom0
        if os.uname()[1] == 'dom0':
            # # Write the script to ~/.qubes-fancy-manager
            # with open(custom_program_path, 'w') as f:
            #     f.write(open(__file__).read())

            # Make the script executable
            # os.chmod(custom_program_path, 0o755)

            # Write the desktop entry to the file
            with open(desktop_entry_file, 'w') as f:
                f.write(desktop_entry)

            # Create a symlink in /usr/share/applications
            os.system(f'sudo ln -s {desktop_entry_file} /usr/share/applications/qubes-fancy-manager.desktop')

            # Restart the Qubes panel to apply the changes
            os.system('xfce4-panel --restart')

        else:
            print("This script should be executed in dom0.")


    def temp_mount_wrap(self, script):
        mount_size = "10G"
        mount_script = f"""
        
        
        # Set the file and mount point paths
        backing_file={self.fancy_mount_path}
        mount_point={self.fancy_mount_point_path}
        
        # Create a file as the backing store for the loop device
        truncate -s {mount_size} "$backing_file"
        
        # Associate the backing file with a loop device
        loop_device=$(losetup --find --show "$backing_file")
        
        # Create the ext4 filesystem on the loop device
        mkfs.ext4 "$loop_device"
        
        # Create the mount point if it doesn't exist
        mkdir -p "$mount_point"
        
        # Mount the loop device
        mount "$loop_device" "$mount_point"
        
        
        """

        unmount_script = f"""
               
        # Unmount the loop device
        umount "$mount_point"
        
        # Detach the loop device
        losetup -d "$loop_device"
        
        # Remove the backing file
        rm "$backing_file"
        
        echo "Unmounted and cleaned up."

        """

        return mount_script + script + unmount_script

    def disp_wrap(self, disp_vm, run_id):

        template_name = f"{run_id}_tmpl"
        disposable_name = f"{run_id}_disp"

        create_disposable = f"""
        
            # Create a template from the default disposable template
            qvm-clone "{disp_vm}" "{template_name}"
            qvm-volume extend "{template_name}:private" 10GiB || true
            
            # Create a disposable qube from the template
            qvm-create --disp --template "{template_name}" "{disposable_name}"

        """

        remove_disposable = f"""
        
            # Wait for the disposable qube to shut down
            qvm-shutdown --wait "{disposable_name}"
            # Remove the disposable qube and template
            qvm-remove -f "{disposable_name}"
            
        """


        return [get_step(create_disposable, False), get_step(remove_disposable, True)], disposable_name

    def require_reboot(self):
        with shelve.open(self.fancy_state_path) as db:
            if 'require_reboot_tmp_file_id' in db:
                return os.path.exists(f"/tmp/{db['require_reboot_tmp_file_id']}")
            return False

    def get_installations(self):
        return self.available_installations

    def get_installation_type(self, installation_id):
        for inst in self.available_installations:
            if inst[0] == installation_id:
                return inst[2]

    def get_install_script(self, installation_id, file_id, default_dispvm, name, netvm, label):
        if self.get_installation_type(installation_id) == "mirage":
            return self.mirage_installation(installation_id, file_id, default_dispvm, name, netvm, label)
        elif self.get_installation_type(installation_id) == "windows":
            return self.windows_installation(installation_id, file_id, default_dispvm, name, netvm, label)
        else:
            return self.unman_installation(installation_id, file_id, default_dispvm, name, netvm, label)

    def mirage_installation(self, installation_id, run_id, default_dispvm, name, netvm, label):
        steps, disposable_name = self.disp_wrap(default_dispvm, run_id)
        script = self.download_file(
            "https://github.com/mirage/qubes-mirage-firewall/releases/download/v0.8.4/mirage-firewall.tar.bz2", run_id,
            disposable_name)
        script = script + self.get_mirage_installation(name, run_id, netvm, label)
        return [steps[0], get_step(script, False), steps[1]]

    def windows_installation(self, installation_id, run_id, default_dispvm, name, netvm, label):

        repo = "https://github.com/im7mortal/qvm-create-windows-qube"
        repo_branch = "qubes-fancy-manager"

        w_inst = installation_id
        w_name = name
        w_net_vm = netvm
        w_packages = "firefox"

        steps, disposable_name = self.disp_wrap(default_dispvm, run_id)


        installation_prepare = """
        
        #!/bin/bash
        # Copyright (C) 2021 Elliot Killick <elliotkillick@zohomail.eu>
        # Licensed under the MIT License. See LICENSE file for details.

        error() {
            exit_code="$?"
            echo -e "${RED}[!]${NC} An unexpected error has occurred! Exiting..." >&2
            exit "$exit_code"
        }

        trap error ERR

        RED='\033[0;31m'
        BLUE='\033[0;34m'
        GREEN='\033[0;32m'
        NC='\033[0m'

        # Step 3
        if [ -f "/usr/lib/qubes/qubes-windows-tools.iso" ]; then
            echo -e "${BLUE}[i]${NC} Qubes Windows Tools is already installed in Dom0. Skipping download..." >&2
        else
            echo -e "${BLUE}[i]${NC} Installing Qubes Windows Tools..." >&2
            if ! sudo qubes-dom0-update -y qubes-windows-tools; then
                echo -e "${RED}[!]${NC} Error installing Qubes Windows Tools! Exiting..." >&2
                exit 1
            fi
            if ! [ -f "/usr/lib/qubes/qubes-windows-tools.iso" ]; then
                echo -e "${RED}[!]${NC} Qubes Windows Tools package is installed, but /usr/lib/qubes/qubes-windows-tools.iso is still missing in Dom0. Exiting..." >&2
                exit 1
            fi
        fi

        echo -e "${BLUE}[i]${NC} Installing package dependencies on $template..." >&2
        fedora_packages="genisoimage geteltorito datefudge"
        debian_packages="genisoimage curl datefudge"
        script='if grep -q '\''ID=fedora'\'' /etc/os-release; then
          sudo dnf -y install '"$fedora_packages"'
        elif grep -q '\''ID=debian'\'' /etc/os-release; then
          sudo apt-get -y install '"$debian_packages"'
        else
          echo "Unsupported distribution."
          exit 1
        fi'
        """ + f"""
        qvm-run -p "{disposable_name}" "$script"
        """ + """

        echo -e "${BLUE}[i]${NC} Cloning qvm-create-windows-qube GitHub repository..." >&2
        """ + f"""
        resources_dir="/home/user/Documents/qvm-create-windows-qube"
        qvm-run -p "{disposable_name}" "cd {"${resources_dir%/*}"} && git clone --branch {repo_branch} {repo}"
        
        """ + """

        echo -e "${BLUE}[i]${NC} Please check for a \"Good signature\" from GPG (Verify it out-of-band if necessary)..." >&2
        """ + f"""
        qvm-run -p "{disposable_name}" "cd '$resources_dir' && gpg --import author.asc && git verify-commit \$(git rev-list --max-parents=0 HEAD)"

        qvm-run -p --filter-escape-chars --no-color-output "$resources_qube" "cat '$resources_dir/qvm-create-windows-qube'" | sudo tee /usr/bin/qvm-create-windows-qube > /dev/null

        # Allow execution of script
        sudo chmod +x /usr/bin/qvm-create-windows-qube

        """ + """
        echo -e "${GREEN}[+]${NC} Installation complete!"


        """ + f"""

                qvm-run -p "{disposable_name}" "cd '$resources_dir'/windows-media/isos && ./download-windows.sh '{w_inst}'"
                echo "START WINDOWS INSTALLATION"
                qvm-create-windows-qube --resources-qube "{disposable_name}" -n {w_net_vm} -oyp {w_packages} -i {w_inst}.iso -a {w_inst}.xml {w_name}
                
                
                """

        return [steps[0], get_step(installation_prepare, False) , steps[1]]

    def unman_installation(self, installation_id, run_id, default_dispvm, name, netvm, label):
        steps, disposable_name = self.disp_wrap(default_dispvm, run_id)
        script = self.download_file(
            f"https://qubes.3isec.org/Templates_4.1/{installation_id}.noarch.rpm", run_id,
            default_dispvm)
        script = script + self.get_unman_installation(name, run_id, netvm, label)
        return [steps[0], get_step(script, False), steps[1]]

    def download_file(self, download_url, destination_id, vm_name):
        return f"""
        echo "start download {download_url}"
        qvm-run -p {vm_name} "if grep -q 'ID=fedora' /etc/os-release; then sudo dnf -y install wget; elif grep -q 'ID=debian' /etc/os-release; then sudo apt-get -y install wget; else echo 'Unsupported distribution.'; exit 1; fi"
        qvm-run -p {vm_name} 'wget --progress=bar:force --show-progress -O /tmp/{destination_id} {download_url}'
        echo "downloaded"
        echo "copy to dom0"
        qvm-run -p {vm_name} 'cat /tmp/{destination_id} ' > /tmp/{destination_id}
        echo "copied to dom0 /tmp/{destination_id}"
        """

    def get_mirage_installation(self, name, file_id, netvm, label):
        return f"""
                
                echo "START EXTRACTION"
                # ensure bzip2 is installed
                sudo dnf install bzip2 bzip2-libs
                mv /tmp/{file_id} /tmp/{file_id}.tar.bz2
                tar jxf /tmp/{file_id}.tar.bz2 -C /tmp
                echo "FINISH EXTRACTION"
                echo "START MIRAGE INSTALLATION"
                mkdir -p /var/lib/qubes/vm-kernels/{name}/
                gzip -n9 < /dev/null > /var/lib/qubes/vm-kernels/{name}/initramfs
                mv /tmp/mirage-firewall/vmlinuz /var/lib/qubes/vm-kernels/{name}/vmlinuz
                qvm-create \
                    --property kernel={name} \
                    --property kernelopts='' \
                    --property memory=32 \
                    --property maxmem=32 \
                    --property netvm={netvm} \
                    --property provides_network=True \
                    --property vcpus=1 \
                    --property virt_mode=pvh \
                    --label={label} \
                    --class StandaloneVM \
                {name}

                qvm-features {name} qubes-firewall 1
                qvm-features {name} no-default-kernelopts 1

                """

    def get_unman_installation(self, name, file_id, netvm, label):
        return f"""
        echo "start to install"
        mv /tmp/{file_id} /tmp/{file_id}.rpm
        qvm-template --keyring /etc/pki/rpm-gpg/RPM-GPG-KEY-unman install /tmp/{file_id}.rpm
        echo "install finished"
        # """

    def unman_key_exist(self, worker_vm):
        unman_key_url = "https://raw.githubusercontent.com/unman/unman/master/unman.pub"
        tmp_file_name = random_string(10)

        script = self.download_file(unman_key_url, tmp_file_name, worker_vm)

        script = script + f"""
        qvm-run -p {worker_vm} 'cat /tmp/{tmp_file_name} ' > /tmp/{tmp_file_name}
        sudo mv /tmp/{tmp_file_name} {self.unman_signing_key}
        sudo rpm --import {self.unman_signing_key}
        """


def random_string(length):
    result = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))
    return result


class LiveShellDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.liveShell = QtWidgets.QTextEdit(self)
        self.liveShell.setReadOnly(True)

        # Set the default size of the QTextEdit widget
        self.liveShell.setMinimumSize(800, 600)

        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.addWidget(self.liveShell)

        self.process = QtCore.QProcess(self)
        self.process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.process.readyRead.connect(self.on_ready_read)
        self.process.finished.connect(self.on_finished)

    def on_ready_read(self):
        text = self.process.readAll().data().decode()
        self.liveShell.moveCursor(QtGui.QTextCursor.End)

        # Check if the output is a progress bar update
        if text.startswith('\r'):
            # Move the cursor one line up and to the beginning of the line
            cursor = self.liveShell.textCursor()
            cursor.movePosition(QtGui.QTextCursor.Up, QtGui.QTextCursor.MoveAnchor)
            cursor.movePosition(QtGui.QTextCursor.StartOfLine, QtGui.QTextCursor.MoveAnchor)
            self.liveShell.setTextCursor(cursor)

            # Remove the current progress line
            cursor = self.liveShell.textCursor()
            cursor.select(QtGui.QTextCursor.LineUnderCursor)
            cursor.removeSelectedText()
            self.liveShell.setTextCursor(cursor)

            # Insert the new progress text
            self.liveShell.insertPlainText(text.lstrip('\r'))

        else:
            self.liveShell.insertPlainText(text)

    def on_finished(self, exit_code):
        self.process.close()
        self.liveShell.append(f"Process finished with exit code {exit_code}.")

    def run_script(self, scripts):
        if not isinstance(scripts, str): # some of installations send string TODO ;
            sc = ""
            for script in scripts:
                sc = sc + script["script"]
            scripts = sc
        print(scripts)
        self.process.start("bash", ["-c", scripts])

class Process(QObject):
    finished = pyqtSignal()
    stdout_ready = pyqtSignal(str)

    @pyqtSlot()
    def run(self):
        script = """
        #!/bin/bash
        for i in {1..10}; do
            echo "Iteration $i"
            sleep 1
        done
        """

        process = subprocess.Popen(script, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        while True:
            line = process.stdout.readline().decode().strip()
            if line:
                self.stdout_ready.emit(line)
            else:
                break

        self.finished.emit()


# pylint: disable=too-few-public-methods
class CreateVMThread(QtCore.QThread):
    def __init__(self, app, vmclass, name, label, template, properties,
                 pool):
        QtCore.QThread.__init__(self)
        self.app = app
        self.vmclass = vmclass
        self.name = name
        self.label = label
        self.template = template
        self.properties = properties
        self.pool = pool
        self.msg = None

    def run(self):

        self.name = "fancy-worker"

        try:
            args = {
                "name": self.name,
                "label": self.label,
                "template": self.template
            }
            if self.pool:
                args['pool'] = self.pool

            vm = self.app.add_new_vm(self.vmclass, **args)

            for k, v in self.properties.items():
                setattr(vm, k, v)

            vm.volumes['private'].resize(61440 * 1024 ** 2)  # 60 GB
        except qubesadmin.exc.QubesException as qex:
            self.msg = str(qex)
        except Exception as ex:  # pylint: disable=broad-except
            self.msg = repr(ex)


class NewWorkerDlg(QtWidgets.QDialog, Ui_NewWorkerDlg):
    def __init__(self, qtapp, app, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self.qtapp = qtapp
        self.app = app

        self.fancy = FancyManager()

        self.thread = None
        self.progress = None
        self.boot_dialog = None

        utils.initialize_widget_with_labels(
            widget=self.label,
            qubes_app=self.app)

        utils.initialize_widget_with_vms(
            widget=self.worker,
            qubes_app=self.app,
            filter_function=(lambda vm: not utils.is_internal(vm) and
                                        vm.klass == 'TemplateVM'),
            allow_none=True)
        print(self.app)
        default_template = self.app.default_template
        for i in range(self.worker.count()):
            print(self.worker.itemData(i))
            if self.worker.itemData(i) == default_template:
                self.worker.setCurrentIndex(i)
                self.worker.setItemText(
                    i, str(default_template) + " (default)")

        self.template_type = "template"

        utils.initialize_widget_with_default(
            widget=self.netvm,
            choices=[(vm.name, vm) for vm in self.app.domains
                     if not utils.is_internal(vm) and
                     getattr(vm, 'provides_network', False)],
            add_none=True,
            add_qubes_default=True,
            default_value=getattr(self.app, 'default_netvm', None))

        try:
            utils.initialize_widget_with_default(
                widget=self.storage_pool,
                choices=[(str(pool), pool) for pool in self.app.pools.values()],
                add_qubes_default=True,
                mark_existing_as_default=True,
                default_value=self.app.default_pool)
        except qubesadmin.exc.QubesDaemonAccessError:
            self.storage_pool.clear()
            self.storage_pool.addItem("(default)", qubesadmin.DEFAULT)

        self.name.setValidator(QtGui.QRegExpValidator(
            QtCore.QRegExp("[a-zA-Z0-9_-]*", QtCore.Qt.CaseInsensitive), None))
        self.name.selectAll()
        self.name.setFocus()

        if self.worker.count() < 1:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr('No template available!'),
                self.tr('Cannot create a qube when no template exists.'))

        type_list = []
        installations = self.fancy.get_installations()
        for inst in self.fancy.get_installations():
            type_list.append((self.tr(inst[0]), inst[1]))

        utils.initialize_widget(widget=self.installlation,
                                choices=type_list,
                                selected_value="please chose installation",
                                add_current_label=False)

        # flag to remove "please chose installation" from options ONCE
        self.initial_option_item_removed = False

        for index, value in enumerate(installations):
            if value[1] == "separator":
                self.installlation.model().item(index).setEnabled(False)
                # self.installlation.insertSeparator(index)
        self.installlation.setItemDelegate(CustomItemDelegate(self.installlation))
        # Load the image and set it to the QLabel
        # pixmap = QtGui.QPixmap(':/')
        # self.imageLabel.setPixmap(pixmap)

        self.installlation.currentIndexChanged.connect(self.installation_change)

        self.worker.currentIndexChanged.connect(self.template_change)

        self.launch_settings.stateChanged.connect(self.settings_change)
        self.install_system.stateChanged.connect(self.install_change)
        # self.createPushButton.clicked.connect(self.create_button_click)

        self.worker_label.setHidden(True)
        self.worker.setHidden(True)
        self.kernel_name_label.setHidden(True)
        self.name.setHidden(True)
        self.label.setHidden(True)
        self.netvm_label.setHidden(True)
        self.netvm.setHidden(True)
        self.launch_settings.setHidden(True)


    def accept(self):

        file_id = "fancy_manager_" + random_string(10)
        name = str(self.name.text())
        label = self.label.currentData()
        netvm = getattr(self.app, 'default_netvm', None)
        if self.netvm.currentIndex() != 0:
            netvm = self.netvm.currentData()


        scripts = self.fancy.get_install_script(self.installlation.currentData(), file_id, self.app.default_dispvm, name,
                                               netvm,
                                               label)
        self.live_shell_dialog = LiveShellDialog(parent=self)
        self.live_shell_dialog.setWindowTitle("Live Output")

        self.live_shell_dialog.show()
        self.live_shell_dialog.run_script(scripts)

        return

        vmclass = self.installlation.currentData()
        name = str(self.name.text())

        if self.install_system.isChecked():
            self.boot_dialog = bootfromdevice.VMBootFromDeviceWindow(
                name, self.qtapp, self.app, self, True)
            if not self.boot_dialog.exec_():
                return

        if name in self.app.domains:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr('Incorrect qube name!'),
                self.tr('A qube with the name <b>{}</b> already exists in the '
                        'system!').format(name))
            return

        label = self.label.currentData()

        template = self.worker.currentData()

        if vmclass in ['AppVM', 'DispVM'] and template is None:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr('Unspecified template'),
                self.tr('{}s must be based on a template!'.format(vmclass)))
            return

        properties = {'provides_network': self.provides_network.isChecked()}
        if self.netvm.currentIndex() != 0:
            properties['netvm'] = self.netvm.currentData()

        # Standalone - not based on a template
        if vmclass == 'StandaloneVM' and template is None:
            properties['virt_mode'] = 'hvm'
            properties['kernel'] = None

        if self.storage_pool.currentData() is not qubesadmin.DEFAULT:
            pool = self.storage_pool.currentData()
        else:
            pool = None

        if self.init_ram.value() > 0:
            properties['memory'] = self.init_ram.value()

        self.thread = CreateVMThread(
            self.app, vmclass, name, label, template, properties, pool)
        self.thread.finished.connect(self.create_finished)
        self.thread.start()

        self.progress = QtWidgets.QProgressDialog(
            self.tr("Creating new qube <b>{0}</b>...").format(name), "", 0, 0)
        self.progress.setCancelButton(None)
        self.progress.setModal(True)
        self.progress.show()

    def create_finished(self):
        if self.thread.msg:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("Error creating the qube!"),
                self.tr("ERROR: {0}").format(self.thread.msg))

        else:
            if self.launch_settings.isChecked():
                subprocess.check_call(['qubes-vm-settings',
                                       str(self.name.text())])
            if self.install_system.isChecked():
                qubesadmin.tools.qvm_start.main(
                    ['--cdrom', self.boot_dialog.cdrom_location,
                     self.name.text()])

        self.progress.hide()
        self.done(0)

    def installation_change(self):
        template = self.worker.currentData()
        klass = self.installlation.currentData()

        for i in self.fancy.get_installations():
            if i[0] == self.installlation.currentData():
                pixmap = QtGui.QPixmap(f':/{i[3]}')
                self.imageLabel.setPixmap(pixmap)

        if not self.initial_option_item_removed and self.installlation.count() > 0:
            last_index = self.installlation.count() - 1
            self.installlation.removeItem(last_index)
            self.initial_option_item_removed = True

        self.worker_label.setHidden(False)
        self.worker.setHidden(False)

        if self.fancy.get_installation_type(klass) == "mirage":
            self.kernel_name_label.setHidden(False)
            self.kernel_name_label.setText("Name of kernel:")
            self.name.setHidden(False)
            self.label.setHidden(False)
            self.netvm_label.setHidden(False)
            self.netvm.setHidden(False)
        elif self.fancy.get_installation_type(klass) == "windows":
            self.kernel_name_label.setHidden(False)
            self.kernel_name_label.setText("Name of windows vm:")
            self.name.setHidden(False)
            self.label.setHidden(True)
            self.netvm_label.setHidden(False)
            self.netvm.setHidden(False)
        else:
            self.kernel_name_label.setHidden(True)
            self.name.setHidden(True)
            self.label.setHidden(True)
            self.netvm_label.setHidden(True)
            self.netvm.setHidden(True)

        if klass in ['TemplateVM', 'StandaloneVM'] and template is None:
            self.install_system.setEnabled(True)
            self.install_system.setChecked(True)
        else:
            self.install_system.setEnabled(False)
            self.install_system.setChecked(False)

        if klass == 'DispVM':
            self.worker.clear()

            for vm in self.app.domains:
                if utils.is_internal(vm):
                    continue
                if vm.klass != 'AppVM':
                    continue
                if getattr(vm, 'template_for_dispvms', True):
                    self.worker.addItem(vm.name, userData=vm)

            self.worker.insertItem(self.worker.count(),
                                        utils.translate("(none)"), None)

            self.worker.setCurrentIndex(0)
            self.template_type = "dispvm"
        elif self.template_type == "dispvm":
            self.worker.clear()

            for vm in self.app.domains:
                if utils.is_internal(vm):
                    continue
                if vm.klass == 'TemplateVM':
                    self.worker.addItem(vm.name, userData=vm)

            self.worker.insertItem(self.worker.count(),
                                        utils.translate("(none)"), None)

            self.worker.setCurrentIndex(0)
            self.template_type = "template"

    def template_change(self):
        template = self.worker.currentData()
        klass = self.installlation.currentData()

        if klass in ['TemplateVM', 'StandaloneVM'] and template is None:
            self.install_system.setEnabled(True)
            self.install_system.setChecked(True)
        else:
            self.install_system.setEnabled(False)
            self.install_system.setChecked(False)

    def install_change(self):
        if self.install_system.isChecked():
            self.launch_settings.setChecked(False)

    def create_button_click(self):
        #
        # print(self.installlation.currentData())
        # return

        print("lol")
        # exit(0)

    def settings_change(self):
        if self.launch_settings.isChecked() and self.install_system.isEnabled():
            self.install_system.setChecked(False)


parser = qubesadmin.tools.QubesArgumentParser()


def main(args=None):
    args = parser.parse_args(args)

    qtapp = QtWidgets.QApplication(sys.argv)

    translator = QtCore.QTranslator(qtapp)
    locale = QtCore.QLocale.system().name()
    i18n_dir = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        'i18n')
    translator.load("qubesmanager_{!s}.qm".format(locale), i18n_dir)
    qtapp.installTranslator(translator)
    QtCore.QCoreApplication.installTranslator(translator)

    qtapp.setOrganizationName('Invisible Things Lab')
    qtapp.setOrganizationDomain('https://www.qubes-os.org/')
    qtapp.setApplicationName(QtCore.QCoreApplication.translate(
        "appname", 'Create qube'))

    dialog = NewVmDlg(qtapp, args.app)
    dialog.exec_()
