import os
import tarfile
import tempfile

ARCHIVE_SUFFIXES = ('.tar.gz', '.tgz', '.tar')


def is_archive_name(name: str) -> bool:
    return any(name.endswith(s) for s in ARCHIVE_SUFFIXES)


def create_tar(path: str) -> str:
    """Create a temporary tar.gz archive for `path` (file or directory).

    Returns the path to the temporary archive (caller should remove it).
    """
    base = os.path.basename(path.rstrip(os.sep)) or '.'
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.tar.gz')
    tmp_name = tmp.name
    tmp.close()
    with tarfile.open(tmp_name, 'w:gz') as tar:
        tar.add(path, arcname=base)
    return tmp_name


def safe_extract_tar(tar_path: str, dest_dir: str):
    """Safely extract `tar_path` into `dest_dir`, preventing path traversal and skipping symlinks.

    Raises an Exception on discovering an illegal path.
    """
    with tarfile.open(tar_path, 'r:*') as tf:
        abs_dest = os.path.abspath(dest_dir)
        for member in tf.getmembers():
            member_path = os.path.join(dest_dir, member.name)
            abs_member = os.path.abspath(member_path)
            if not (abs_member == abs_dest or abs_member.startswith(abs_dest + os.sep)):
                raise Exception(f"Illegal path in archive: {member.name}")

        for member in tf.getmembers():
            member_path = os.path.join(dest_dir, member.name)
            if member.isdir():
                os.makedirs(member_path, exist_ok=True)
            elif member.issym() or member.islnk():
                # skip symlinks for safety
                continue
            else:
                parent = os.path.dirname(member_path)
                os.makedirs(parent, exist_ok=True)
                f = tf.extractfile(member)
                if f is None:
                    continue
                with open(member_path, 'wb') as out_f:
                    out_f.write(f.read())
