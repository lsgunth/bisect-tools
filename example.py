#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
# Copyright Logan Gunthorpe <logang@deltatee.com>

import re
from bisect_tools import *

script_path = Path(__file__).resolve().parent

kern = Kernel(kernel_path=Path("~/linux").expanduser(),
              tftp_path=Path("/srv/tftp/vmlinuz"),
              use_icecc=True, use_ccache=True,
              concurrency=40)

remote = Remote("<host>", "<ipmi_host>", "<ipmi_user>", "<ipmi_pass>",
                reboot_command="/lib/molly-guard/reboot",
                ssh_id=script_path / "id_rsa")

log_path = log_path(kern, Path("logs"))

logger = logging.getLogger("test")
logger.info("Logging to %s", log_path)

kern.bisect_log(log_file=log_path / "bisect.log")

kern.build(log_file=log_path / "make.log")
kern.install()

match = re.compile(r"RIP")

with RemoteMonitor(remote, match, log_path / "dmesg.log") as rm:
    try:
        remote.reboot_wait()
        remote.wait_for_host_up()
        logger.info("Running: %s", remote.kernel_version())
    except RemoteMonitorInterrupt as e:
        rm.wait_for_silence()
        bisect_bad()
    except (RemoteWaitUpTimeout, RemoteRebootFailure):
        bisect_stop()
    except Exception as e:
        logging.error(e)
        bisect_stop()
    else:
        bisect_good()
