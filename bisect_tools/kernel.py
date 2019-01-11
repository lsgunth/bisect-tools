# SPDX-License-Identifier: GPL-2.0
# Copyright Logan Gunthorpe <logang@deltatee.com>

import os
import shutil
import logging
import subprocess as sp

logger = logging.getLogger("kernel")

class Kernel(object):
    def __init__(self, kernel_path, tftp_path, use_icecc=False,
                 use_ccache=False, concurrency=16):

        self.kernel_path = kernel_path
        self.tftp_path = tftp_path
        self.concurrency = concurrency
        self.env = os.environ

        if use_icecc and use_ccache:
            self.args = ["CC=ccache icecc gcc"]
        elif use_icecc:
            self.args = ["CC='icecc gcc'"]
        elif use_ccache:
            self.args = ["CC='ccache gcc'"]

        if use_ccache:
            self.env["KBUILD_BUILD_TIMESTAMP"] = ""

    def build(self, log_file=None):
        if log_file:
            log_file = log_file.open("w")

        logger.info("Building Kernel: %s", self.kernel_path)

        cmd = ["make", "-C", str(self.kernel_path),
                "-j", str(self.concurrency)]  + self.args

        sp.run(cmd + ["olddefconfig", "all"],
               stdout=log_file, stderr=log_file,
               env=self.env, check=True)

        logger.info("Build Complete")

    def install(self):
        shutil.copy(str(self.kernel_path / "arch" / "x86" / "boot" / "bzImage"),
                    str(self.tftp_path))

        logger.info("Kernel installed in %s", self.tftp_path)
