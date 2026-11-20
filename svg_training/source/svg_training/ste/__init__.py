"""STE's own learning track (ste_learning/). No module here imports PyTorch or Isaac when it is imported.

``config``: the settings loader (task L0.1). Process tooling (task L0.7, Linux only): ``shared`` (the one shared folder
of live process state), ``pauses`` (the owner's pauses, merged from every pause log), ``state`` and ``atomic`` (the
state file, whole-file writes), ``run_contract`` (what every trainer does: resume, stop, cap, non-finite values),
``jobs`` (launch, wait, status; the command line is ``scripts/ste_job.py``), ``budget`` (the GPU-hour ledger)."""
