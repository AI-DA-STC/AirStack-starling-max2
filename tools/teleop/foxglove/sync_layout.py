#!/usr/bin/env python3
"""Put the shipped Foxglove layout into Studio's layout store as the layout's `working` copy.

Run by localisation/scripts/slam_up.sh before Studio starts (never while it runs). Prints the chosen
layout id as the only stdout line, or nothing. Messages go to stderr. Always exits 0: a problem here
must never stop a session. Only `working` is written, so nothing is pushed to a Foxglove account.
"""
import argparse, copy, datetime, hashlib, json, os, pathlib, sys, tempfile

PANEL = "3D!cuvslam"


def _load(path):
    try:
        d = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) and isinstance(d.get("id"), str) else None


def _find(store, name):
    found = []
    try:
        dirs = sorted(p for p in store.glob("layouts-*") if p.is_dir())
    except OSError:
        return found
    for d in dirs:
        try:
            files = sorted(f for f in d.iterdir() if f.is_file())
        except OSError:
            continue
        for f in files:
            lay = _load(f)
            if lay is not None and lay.get("name") == name:
                found.append((str(lay.get("lastViewedAt") or ""), f, lay))
    return found


def _camera(layout):
    for key in ("working", "baseline"):
        try:
            return layout[key]["data"]["configById"][PANEL]["cameraState"]
        except (KeyError, TypeError):
            continue
    return None


def _now():
    t = datetime.datetime.now(datetime.timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (t.microsecond // 1000)


def _write_atomic(target, text, tmp_dir):
    fd, tmp = tempfile.mkstemp(dir=tmp_dir, prefix=".sync_layout.")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def run(args):
    store = pathlib.Path(args.store)
    found = _find(store, args.name)
    if not found:
        print("sync_layout: no layout named %r in %s. Import it once: Layouts -> Import from file -> "
              "/teleop-foxglove/teleop-cuvslam.json" % (args.name, store), file=sys.stderr)
        return
    _, path, layout = max(found, key=lambda t: t[0])
    lid = layout["id"]
    raw = pathlib.Path(args.layout).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    marker = pathlib.Path(args.marker)
    try:
        if marker.read_text().split() == [digest, lid]:
            print(lid)
            return
    except OSError:
        pass
    shipped = json.loads(raw)
    cam = _camera(layout)
    if cam is not None and isinstance(shipped.get("configById", {}).get(PANEL), dict):
        shipped["configById"][PANEL]["cameraState"] = copy.deepcopy(cam)
    new = dict(layout)
    new["working"] = {"data": shipped, "savedAt": _now()}
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bdir = pathlib.Path(args.backup_dir)
    bdir.mkdir(parents=True, exist_ok=True)
    bk = bdir / ("%s.%s.json" % (lid, stamp))
    bk.write_bytes(path.read_bytes())
    _write_atomic(path, json.dumps(new, indent=2), store)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("%s %s\n" % (digest, lid))
    print("sync_layout: shipped layout loaded into %s (backup %s)" % (lid, bk), file=sys.stderr)
    print(lid)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True)
    ap.add_argument("--layout", required=True)
    ap.add_argument("--name", default="teleop-cuvslam")
    ap.add_argument("--marker", required=True)
    ap.add_argument("--backup-dir", required=True)
    try:
        args = ap.parse_args(argv)
        run(args)
    except SystemExit:
        pass
    except Exception as e:  # never stop a session
        print("sync_layout: skipped (%s: %s)" % (type(e).__name__, e), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
