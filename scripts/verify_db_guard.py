"""Fail closed before standalone verification scripts import the WMS app."""
import os
import sys
from contextlib import contextmanager


def require_owned_test_profile():
    """Read the real Windows LPAC token and return its private synthetic profile."""
    if os.name != 'nt':
        raise SystemExit('安全阻断：此入口尚未证明当前系统的测试文件隔离')
    import ctypes as c
    from ctypes import wintypes as w
    from pathlib import Path
    import re

    kernel = c.WinDLL('kernel32', use_last_error=True)
    advapi = c.WinDLL('advapi32', use_last_error=True)
    userenv = c.WinDLL('userenv', use_last_error=True)
    ole = c.WinDLL('ole32', use_last_error=True)
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.LocalFree.argtypes = [c.c_void_p]
    ole.CoTaskMemFree.argtypes = [c.c_void_p]
    advapi.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, c.POINTER(w.HANDLE)]
    advapi.GetTokenInformation.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.POINTER(w.DWORD)]
    advapi.GetLengthSid.argtypes = [c.c_void_p]
    advapi.GetLengthSid.restype = w.DWORD
    advapi.ConvertSidToStringSidW.argtypes = [c.c_void_p, c.POINTER(w.LPWSTR)]
    userenv.GetAppContainerFolderPath.argtypes = [w.LPCWSTR, c.POINTER(w.LPWSTR)]
    userenv.GetAppContainerFolderPath.restype = c.c_long
    token, sid_text, folder = w.HANDLE(), w.LPWSTR(), w.LPWSTR()

    class Unicode(c.Structure):
        _fields_ = [('Length', w.WORD), ('MaximumLength', w.WORD), ('Buffer', c.c_void_p)]
    class Attribute(c.Structure):
        _fields_ = [('Name', Unicode), ('ValueType', w.WORD), ('Reserved', w.WORD),
                    ('Flags', w.DWORD), ('ValueCount', w.DWORD), ('Values', c.c_void_p)]
    class Attributes(c.Structure):
        _fields_ = [('Version', w.WORD), ('Reserved', w.WORD), ('Count', w.DWORD), ('Items', c.c_void_p)]

    def info(kind):
        size = w.DWORD()
        advapi.GetTokenInformation(token, kind, None, 0, c.byref(size))
        minimum = {29: c.sizeof(w.DWORD), 39: c.sizeof(Attributes), 31: c.sizeof(c.c_void_p)}[kind]
        if not minimum <= size.value <= 1024 * 1024:
            raise ValueError('invalid token buffer size')
        data = c.create_string_buffer(size.value)
        if not advapi.GetTokenInformation(token, kind, data, size.value, c.byref(size)):
            raise ValueError('cannot query token')
        return data

    def within(data, pointer, size):
        start = c.addressof(data)
        if not pointer or size < 0 or not start <= pointer <= pointer + size <= start + c.sizeof(data):
            raise ValueError('invalid token pointer')
        return pointer

    try:
        if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 8, c.byref(token)):
            raise ValueError('cannot query process token')
        is_container = info(29)
        if c.cast(is_container, c.POINTER(w.DWORD)).contents.value != 1:
            raise ValueError('not an AppContainer')
        data = info(39)
        attributes = c.cast(data, c.POINTER(Attributes)).contents
        if attributes.Version != 1 or not 0 < attributes.Count < 100:
            raise ValueError('invalid token attributes')
        within(data, attributes.Items, attributes.Count * c.sizeof(Attribute))
        items = c.cast(attributes.Items, c.POINTER(Attribute))
        lpac = False
        for index in range(attributes.Count):
            item = items[index]
            if item.Name.Length % 2 or item.Name.Length > item.Name.MaximumLength:
                raise ValueError('invalid token name')
            within(data, item.Name.Buffer, item.Name.Length)
            name = c.wstring_at(item.Name.Buffer, item.Name.Length // 2)
            if name == 'WIN://NOALLAPPPKG':
                within(data, item.Values, 8)
                lpac = (item.ValueType in (1, 2) and item.ValueCount == 1 and not item.Flags & 16
                        and c.cast(item.Values, c.POINTER(c.c_uint64)).contents.value == 1)
        if not lpac:
            raise ValueError('not an LPAC')
        container = info(31)
        package = c.cast(container, c.POINTER(c.c_void_p)).contents.value
        within(container, package, 8)
        within(container, package, advapi.GetLengthSid(package))
        if not advapi.ConvertSidToStringSidW(package, c.byref(sid_text)):
            raise ValueError('cannot identify package')
        if userenv.GetAppContainerFolderPath(sid_text, c.byref(folder)) != 0 or not folder:
            raise ValueError('cannot identify profile')
        profile = Path(folder.value)
        if profile.name != 'AC' or not re.fullmatch(r'wms\.synthetic\.[0-9a-f]{32}', profile.parent.name):
            raise ValueError('not a synthetic test profile')
        return profile
    except (ValueError, OSError, TypeError) as exc:
        raise SystemExit('安全阻断：未取得真实 LPAC 合成测试身份') from exc
    finally:
        if folder:
            ole.CoTaskMemFree(c.cast(folder, c.c_void_p))
        if sid_text:
            kernel.LocalFree(c.cast(sid_text, c.c_void_p))
        if token:
            kernel.CloseHandle(token)


def validate_owned_test_file(value):
    """Reject paths outside the OS-owned profile before inspecting a file."""
    from pathlib import Path
    import stat
    profile = require_owned_test_profile()
    text = os.fspath(value)
    if not isinstance(text, str) or text.startswith(('\\\\', '//')) or not os.path.isabs(text):
        raise SystemExit('安全阻断：测试文件必须使用隔离身份内的绝对普通路径')
    path = Path(os.path.abspath(text))
    base = os.path.normcase(os.path.abspath(profile))
    if (any(':' in part or '~' in part for part in path.parts[1:])
            or os.path.commonpath((os.path.normcase(str(path)), base)) != base or path == profile):
        raise SystemExit('安全阻断：测试文件不属于当前隔离身份')
    chain, current = [], path
    while current != profile:
        chain.append(current)
        current = current.parent
    chain.append(profile)
    for item in reversed(chain):
        status = item.lstat()
        if stat.S_ISLNK(status.st_mode) or getattr(status, 'st_file_attributes', 0) & 1024:
            raise SystemExit('安全阻断：测试路径存在链接或重解析点')
    status = path.stat()
    if not stat.S_ISREG(status.st_mode) or status.st_nlink != 1:
        raise SystemExit('安全阻断：测试目标不是独占普通文件')
    return path


@contextmanager
def owned_test_file(value):
    """Keep ordinary file and parent handles pinned throughout the read."""
    path = validate_owned_test_file(value)
    profile = require_owned_test_profile()
    import ctypes as c
    from ctypes import wintypes as w

    class FileInfo(c.Structure):
        _fields_ = [('Attributes', w.DWORD), ('Created', w.FILETIME), ('Accessed', w.FILETIME),
                    ('Written', w.FILETIME), ('Volume', w.DWORD), ('SizeHigh', w.DWORD),
                    ('SizeLow', w.DWORD), ('Links', w.DWORD), ('IndexHigh', w.DWORD), ('IndexLow', w.DWORD)]

    kernel = c.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, c.c_void_p, w.DWORD, w.DWORD, w.HANDLE]
    kernel.CreateFileW.restype = w.HANDLE
    kernel.GetFileInformationByHandle.argtypes = [w.HANDLE, c.POINTER(FileInfo)]
    kernel.GetFinalPathNameByHandleW.argtypes = [w.HANDLE, w.LPWSTR, w.DWORD, w.DWORD]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    chain, current = [], path
    while current != profile:
        chain.append(current)
        current = current.parent
    chain.append(profile)
    handles, volume = [], None
    try:
        for item in reversed(chain):
            # OPEN_REPARSE_POINT prevents following a swapped link. No shared
            # WRITE or DELETE: the checked object cannot be replaced mid-read.
            # READ_ATTRIBUTES alone does not participate in Windows sharing
            # exclusion; use actual read access so WRITE/DELETE sharing is denied.
            handle = kernel.CreateFileW(str(item), 0x80000000, 1, None, 3, 0x02200000, None)
            if handle in (None, c.c_void_p(-1).value):
                raise OSError(c.get_last_error(), '无法锁定本次隔离文件路径')
            handles.append(handle)
            info = FileInfo()
            if not kernel.GetFileInformationByHandle(handle, c.byref(info)):
                raise OSError(c.get_last_error(), '无法核对隔离文件身份')
            if info.Attributes & 1024 or bool(info.Attributes & 16) != (item != path):
                raise SystemExit('安全阻断：隔离文件类型或链接状态已变化')
            if item == path and info.Links != 1:
                raise SystemExit('安全阻断：隔离文件出现额外硬链接')
            if volume is None:
                volume = info.Volume
            if info.Volume != volume:
                raise SystemExit('安全阻断：隔离路径跨越磁盘卷')
            buffer = c.create_unicode_buffer(32768)
            # LPAC cannot query the host's DOS drive mapping. The opened
            # volume-relative name plus the pinned volume and non-reparse
            # ancestor handles establish the same checked path without it.
            length = kernel.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0x0c)
            if not 0 < length < len(buffer):
                raise SystemExit('安全阻断：无法核对隔离文件最终路径')
            final = buffer.value
            expected = str(item)[len(item.drive):]
            if not final.startswith('\\') or os.path.normcase(final) != os.path.normcase(expected):
                raise SystemExit('安全阻断：隔离路径别名或归属已变化')
        yield path
    finally:
        for handle in reversed(handles):
            kernel.CloseHandle(handle)


def require_synthetic_memory_database():
    """Reject inherited database targets and any preloaded application/config."""
    memory_uri = 'sqlite:///:memory:'
    for key in ('DATABASE_URL', 'WMS_DATABASE_URI'):
        if os.environ.get(key, '') not in ('', memory_uri):
            raise SystemExit('安全阻断：独立验证仅允许新建内存数据库')
    if os.environ.get('FLASK_ENV', '') not in ('', 'testing'):
        raise SystemExit('安全阻断：独立验证仅允许 testing 环境')
    if any(name == 'app' or name.startswith('app.') or name == 'config'
           for name in sys.modules):
        raise SystemExit('安全阻断：应用或配置已预加载，无法证明数据库目标')
    os.environ['DATABASE_URL'] = memory_uri
    os.environ['WMS_DATABASE_URI'] = memory_uri
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['WMS_SKIP_AUTO_UPDATE'] = '1'
    os.environ['WMS_SKIP_STARTUP_BACKUP'] = '1'


def _require_isolated_test_runtime():
    """Accept only a parent-issued, OS-bound capability in the synthetic LPAC job.

    A memory URI or a JSON file is not proof. The read handle must refer to the
    inaccessible supervisor directory, bind this exact process creation time,
    and attest checks performed before the suspended process was resumed.
    Descendants need their own capability; inherited environment alone is refused.
    """
    import ctypes as c
    from ctypes import wintypes as w
    import hashlib
    import json
    from pathlib import Path
    profile = require_owned_test_profile()
    def _deny():
        raise SystemExit('安全阻断：未取得绑定当前进程的隔离运行能力')
    for name in ('DATABASE_URL', 'WMS_DATABASE_URI'):
        if os.environ.get(name) != 'sqlite:///:memory:':
            _deny()
    if os.environ.get('FLASK_ENV') != 'testing':
        _deny()
    raw = os.environ.get('WMS_TEST_RUNTIME_HANDLE', '')
    if not raw.isascii() or not raw.isdecimal() or not 0 < int(raw) < 2**63 or int(raw) % 4:
        _deny()
    kernel=c.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=w.HANDLE
    kernel.GetFileType.argtypes=[w.HANDLE]
    kernel.GetFinalPathNameByHandleW.argtypes=[w.HANDLE,w.LPWSTR,w.DWORD,w.DWORD]
    kernel.CreateFileW.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD,c.c_void_p,w.DWORD,w.DWORD,w.HANDLE]
    kernel.CreateFileW.restype=w.HANDLE
    kernel.CloseHandle.argtypes=[w.HANDLE]
    kernel.GetProcessTimes.argtypes=[w.HANDLE,c.POINTER(w.FILETIME),c.POINTER(w.FILETIME),c.POINTER(w.FILETIME),c.POINTER(w.FILETIME)]
    kernel.IsProcessInJob.argtypes=[w.HANDLE,w.HANDLE,c.POINTER(w.BOOL)]
    kernel.GetFileSizeEx.argtypes=[w.HANDLE,c.POINTER(c.c_int64)]
    kernel.SetFilePointerEx.argtypes=[w.HANDLE,c.c_int64,c.POINTER(c.c_int64),w.DWORD]
    kernel.ReadFile.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,c.POINTER(w.DWORD),c.c_void_p]
    handle=w.HANDLE(int(raw));size=c.c_int64();buffer=c.create_unicode_buffer(32768)
    if kernel.GetFileType(handle)!=1 or not kernel.GetFileSizeEx(handle,c.byref(size)) or not 0<size.value<=16384:
        _deny()
    count=kernel.GetFinalPathNameByHandleW(handle,buffer,len(buffer),0x0c)
    if not 0<count<len(buffer) or not buffer.value.startswith(chr(92)) or buffer.value.startswith(chr(92)*2):
        _deny()
    proof_path=Path(profile.drive+buffer.value)
    expected_name=profile.parent.name+'.runtime.json'
    if (proof_path.name!=expected_name or not proof_path.parent.name.startswith('wms-supervisor-state-')
            or proof_path.is_relative_to(profile) or not proof_path.is_absolute()):
        _deny()
    # The LPAC cannot create or alter the issuer's file. Merely passing an fd to
    # an attacker-authored file inside its own profile cannot satisfy this check.
    for target,flags,rights in [(proof_path,0x00200000,value) for value in (0x40000000,0x10000,0x40000)] + [(proof_path.parent,0x02200000,value) for value in (2,4,0x10000,0x40000)]:
        candidate=kernel.CreateFileW(str(target),rights,7,None,3,flags,None)
        if candidate!=c.c_void_p(-1).value:
            kernel.CloseHandle(candidate);_deny()
        if c.get_last_error()!=5:
            _deny()
    if not kernel.SetFilePointerEx(handle,0,None,0):
        _deny()
    data=c.create_string_buffer(size.value);read=w.DWORD()
    if not kernel.ReadFile(handle,data,size.value,c.byref(read),None) or read.value!=size.value:
        _deny()
    try:proof=json.loads(data.raw)
    except (ValueError,UnicodeError):_deny()
    times=[w.FILETIME() for _ in range(4)]
    if not kernel.GetProcessTimes(kernel.GetCurrentProcess(),*(c.byref(t) for t in times)):
        _deny()
    created=(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime
    inside=w.BOOL()
    if not kernel.IsProcessInJob(kernel.GetCurrentProcess(),None,c.byref(inside)) or not inside.value:
        _deny()
    source=Path(__file__).resolve().parents[1]
    if (not isinstance(proof,dict) or proof.get('schema')!=1 or proof.get('run_id')!=profile.parent.name
            or proof.get('pid')!=os.getpid() or proof.get('created_filetime')!=created
            or proof.get('source')!=str(source) or proof.get('runtime')!=sys.executable
            or proof.get('database')!='sqlite:///:memory:'
            or any(proof.get(k) is not True for k in ('job_assigned_at_creation','network_filters_verified','readonly_source'))
            or proof.get('app_sha256')!=hashlib.sha256((source/'app/app.py').read_bytes()).hexdigest()):
        _deny()
    return profile


def require_isolated_test_runtime():
    """Fail closed for stale or forged native handles before any application import."""
    try:
        return _require_isolated_test_runtime()
    except (OSError, ValueError, TypeError, OverflowError):
        raise SystemExit('安全阻断：隔离运行能力无效') from None
