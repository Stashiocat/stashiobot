import psutil
from ctypes import *
from ctypes.wintypes import *
import win32con

STANDARD_RIGHTS_REQUIRED = 0x000F0000
SYNCHRONIZE = 0x00100000
PROCESS_ALL_ACCESS = (STANDARD_RIGHTS_REQUIRED | SYNCHRONIZE | 0xFFF)
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010

class ErrorReadingMemoryException(Exception):
    pass

class MODULEENTRY32(Structure):
    _fields_ = [ ( 'dwSize' , DWORD ) , 
                 ( 'th32ModuleID' , DWORD ),
                 ( 'th32ProcessID' , DWORD ),
                 ( 'GlblcntUsage' , DWORD ),
                 ( 'ProccntUsage' , DWORD ) ,
                 ( 'modBaseAddr' , c_longlong ) ,
                 ( 'modBaseSize' , DWORD ) , 
                 ( 'hModule' , HMODULE ) ,
                 ( 'szModule' , c_char * 256 ),
                 ( 'szExePath' , c_char * 260 ) ]

class RetroarchReader():
    def __init__(self):
        self.open_handle = 0
        self.wram_address = 0
        pass
        
    def open_process(self):
        assert 0 == self.open_handle, "Process already opened."
        
        pid = self.get_retroarch_process()
        
        if pid == -1:
            return False
        
        access_flags = win32con.PROCESS_ALL_ACCESS
        self.open_handle = windll.kernel32.OpenProcess(access_flags, False, pid)
        
        libretro_wram = self.get_snes9x_libretro_wram_address(pid)
        
        if 0 == libretro_wram:
            if self.open_handle:
                self.close_process()
            return False
        
        wram_ptr = c_ulonglong()
        bytesRead = c_ulonglong()
        
        r = windll.kernel32.ReadProcessMemory(self.open_handle, libretro_wram, byref(wram_ptr), sizeof(wram_ptr), byref(bytesRead))
        
        if r == 0:
            self.close_process()
            return False

        self.wram_address = wram_ptr.value
        
        return True
        
    def close_process(self):
        assert 0 != self.open_handle, "Process isn't opened"
        
        windll.kernel32.CloseHandle(self.open_handle)
        self.open_handle = 0
        self.wram_address = 0
        
    def get_retroarch_process(self):
        pids = psutil.pids()
        
        for p in pids:
            try:
                proc = psutil.Process(p)
                if proc.name() == 'retroarch.exe':
                    return proc.pid
            except:
                pass
                
        return -1
        
    def get_snes9x_libretro_wram_address(self, pid):
        hModule = c_void_p(0)
        hModule = windll.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)

        m32 = MODULEENTRY32()
        m32.dwSize = sizeof(MODULEENTRY32)

        ret = windll.kernel32.Module32First(hModule, pointer(m32))
        if ret == 0:
            print(f"Failed Module32First: {windll.kernel32.GetLastError()}")
            return 0
            
        base_address = m32.modBaseAddr
        mod_base_address = 0
        
        found_base_address = False
        while ret:
            if m32.szModule == b'snes9x_libretro.dll':
                mod_base_address = m32.modBaseAddr
                found_base_address = True
                break
            ret = windll.kernel32.Module32Next(hModule, pointer(m32))
            
        windll.kernel32.CloseHandle(hModule)
        
        if not found_base_address:
            return 0
        
        # don't judge me
        wram_offset = 0x2C9B08
        return mod_base_address + wram_offset
        
    def __alloc_mem(self, num_bytes):
        if num_bytes == 1:
            return c_ubyte()
        elif num_bytes == 2:
            return c_ushort()
        elif num_bytes == 4:
            return c_ulong()
        elif num_bytes == 8:
            return c_ulonglong()
        
    def read_memory(self, wram_addr, num_bytes):
        if 0 == self.open_handle:
            raise ErrorReadingMemoryException
        
        out_val = self.__alloc_mem(num_bytes)
        bytesRead = c_ulonglong()
        
        r = windll.kernel32.ReadProcessMemory(self.open_handle, self.wram_address + wram_addr, byref(out_val), sizeof(out_val), byref(bytesRead))
        
        if 0 == r:
            self.close_process()
            raise ErrorReadingMemoryException
            return 0
            
        return out_val.value
