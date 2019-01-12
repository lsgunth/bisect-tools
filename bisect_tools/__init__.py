# SPDX-License-Identifier: GPL-2.0
# Copyright Logan Gunthorpe <logang@deltatee.com>

from .remote import Remote, RemoteMonitor, RemoteMonitorInterrupt
from .kernel import Kernel

import logging
from pathlib import Path

def log_path(kernel, path=Path(".")):
    run = 1
    kern_ver = kernel.describe()

    ret = path / kern_ver

    while ret.exists():
        run += 1
        ret = path / (kern_ver + "_run{}".format(run))

    ret.mkdir(parents=True)

    logging.basicConfig(level=logging.INFO,
        format='%(asctime)s %(levelname)-5s - %(name)-8s: %(message)s',
        handlers=[logging.FileHandler(str(ret / "test.log")),
                  logging.StreamHandler()])

    return ret
