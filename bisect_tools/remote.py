# SPDX-License-Identifier: GPL-2.0
# Copyright Logan Gunthorpe <logang@deltatee.com>

import time
import logging
import subprocess as sp

logger = logging.getLogger("remote")

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

    def pxe_boot(self):
        logger.debug("Set PXE boot")
        sp.run(self.ipmi_args + ["chassis", "bootdev", "pxe"], check=True)

    def command(self, *cmd, check=True):
        logger.debug("Remote Command: %s", " ".join(cmd))
        return sp.run(self.ssh_args + list(cmd), check=check,
                      stdout=sp.PIPE, universal_newlines=True)

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

    def _wait_for_host(self, timeout=None, expect=True):

        if timeout is not None:
            end = time.time() + timeout

        while True:
            if timeout is not None and time.time() > end:
                return False

            if self.is_host_up() == expect:
                return True

            time.sleep(0.2)

    def wait_for_host_down(self, *args, **kwargs):
        self._wait_for_host(expect=False, *args, **kwargs)

    def wait_for_host_up(self, *args, **kwargs):
        self._wait_for_host(expect=True, *args, **kwargs)

    def kernel_version(self):
        ret = self.command("uname", "-r")
        ver = ret.stdout.strip()
        logger.debug("Kernel Version: %s", ver)
        return ver
