# SPDX-License-Identifier: GPL-2.0
# Copyright Logan Gunthorpe <logang@deltatee.com>

import os
import pty
import time
import logging
import threading
import subprocess as sp

logger = logging.getLogger("remote")

class RemoteMonitorInterrupt(Exception):
    def __init__(self, line):
        self.line = line
        super().__init__("Remote Monitor Interrupt")

class Remote(object):
    def __init__(self, host, ipmi_host, ipmi_username, ipmi_password,
                 ssh_user="root", ssh_id=None, ssh_port=22,
                 reboot_command="/sbin/reboot"):
        self.ipmi_args = ["ipmitool", "-I", "lanplus", "-H", ipmi_host,
                          "-U", ipmi_username, "-P", ipmi_password]
        self.host = host
        self.ssh_port = ssh_port

        self.ssh_args = ["ssh", self.host, "-p", str(self.ssh_port),
                         "-l", ssh_user]

        if ssh_id:
            self.ssh_args += ["-i", str(ssh_id)]

        self.reboot_command = reboot_command

        self.intr_line = None
        self.intr_event = threading.Event()

        self.devnull = open(os.devnull, "w")

    def pxe_boot(self):
        logger.debug("Set PXE boot")
        sp.run(self.ipmi_args + ["chassis", "bootdev", "pxe"],
               check=True, stdout=self.devnull, stderr=self.devnull)

    def command(self, *cmd, check=True):
        logger.debug("Remote Command: %s", " ".join(cmd))
        return sp.run(self.ssh_args + list(cmd), check=check,
                      stdout=sp.PIPE, stderr=self.devnull,
                      universal_newlines=True)

    def reboot(self):
        self.pxe_boot()
        self.command("/lib/molly-guard/reboot", check=False)

    def reboot_wait(self):
        self.reboot()
        self.wait_for_host_down()

    def ipmi_reboot(self, kind="soft"):
        if kind not in ["soft", "reset", "cycle"]:
            raise ValueError("Invalid reboot type")

        logger.debug("Reboot: %s", kind)
        sp.run(self.ipmi_args + ["chassis", "power", kind], check=True)

    def is_host_up(self):
        ret = sp.run(["nc", "-z", self.host, str(self.ssh_port), "-w", "1"])

        if ret.returncode == 0:
            logger.debug("Host is Up")
        else:
            logger.debug("Host is Down")

        return ret.returncode == 0

    def interrupt(self, line):
        self.intr_line = line
        self.intr_event.set()

    def _wait_for_host(self, timeout=None, expect=True):

        self.intr_event.clear()

        if timeout is not None:
            end = time.time() + timeout

        while True:
            if timeout is not None and time.time() > end:
                return False

            if self.is_host_up() == expect:
                return True

            if self.intr_event.wait(0.5):
                logger.info("Found interrupt line")
                raise RemoteMonitorInterrupt(self.intr_line)

    def wait_for_host_down(self, *args, **kwargs):
        self._wait_for_host(expect=False, *args, **kwargs)

    def wait_for_host_up(self, *args, **kwargs):
        logger.info("Waiting for host to go up")
        self._wait_for_host(expect=True, *args, **kwargs)

    def kernel_version(self):
        ret = self.command("uname", "-r")
        ver = ret.stdout.strip()
        logger.debug("Kernel Version: %s", ver)
        return ver

class RemoteMonitor(threading.Thread):
    def __init__(self, remote, match, log_file=None):
        self.remote = remote
        self.log_file = log_file
        self.stopped = False
        self.proc = None
        self.master = None
        self.slave = None
        self.match = match
        self.silence_event = threading.Event()

        if self.log_file is not None:
            self.log_file = self.log_file.open("wb")

        super().__init__()

    def deactivate(self):
        devnull = self.remote.devnull
        sp.run(self.remote.ipmi_args + ["sol", "deactivate"],
               stdout=devnull, stderr=devnull)

    def __enter__(self):
        self.deactivate()
        self.start()
        return self

    def __exit__(self, *args):
        self.stopped = True
        if self.master:
            os.write(self.master, b"~.")
        if self.proc:
            self.proc.wait(5.0)
            self.proc.kill()
        if self.slave:
            os.close(self.slave)
        self.deactivate()
        self.join()

    def run(self):
        self.master, self.slave = pty.openpty()
        master = os.fdopen(self.master, "rb")
        self.proc = sp.Popen(self.remote.ipmi_args + ["sol", "activate"],
                             stdout=self.slave, stderr=self.slave,
                             stdin=self.slave)

        while not self.stopped:
            line = master.readline()
            if not line:
                continue

            self.silence_event.set()

            if self.log_file:
                self.log_file.write(line)
                self.log_file.flush()

            try:
                if self.match.search(line.decode()):
                    self.remote.interrupt(line)
            except UnicodeDecodeError:
                pass

    def wait_for_silence(self, silent_time=5.0):
        logger.info("Waiting for dmesg silence")
        while self.silence_event.wait(silent_time):
            self.silence_event.clear()
