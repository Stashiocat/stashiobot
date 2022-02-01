import websockets
import asyncio
import json
import struct
import math
import sys

class BaseAddressConverter():
    def __init__(self, rom_base, wram_base, sram_base):
        self.__rom_base = rom_base
        self.__wram_base = wram_base
        self.__sram_base = sram_base
        
    def get_rom_addr(self, addr):
        return self.__rom_base + addr
        
    def get_wram_addr(self, addr):
        return self.__wram_base + addr
        
    def get_sram_addr(self, addr):
        return self.__sram_base + addr
        
class SnesAddressConverter(BaseAddressConverter):
    def __init__(self):
        super().__init__(
            rom_base=0x000000,
            wram_base=0xF50000,
            sram_base=0xE00000
        )

class SnesDevice():
    def __init__(self, qusb2snes, device_name):
        self.__addr_converter = SnesAddressConverter()
        self.__qusb2snes = qusb2snes
        self.__device_name = device_name
        
    async def read_wram(self, addr, size):
        return await self.__qusb2snes.read_wram(self.__addr_converter.get_wram_addr(addr), size)
        
    async def read_wram_batch(self, addr_and_sizes):
        converted = [(self.__addr_converter.get_wram_addr(addr), size) for addr, size in addr_and_sizes]
        return await self.__qusb2snes.read_wram_batch(converted)
        
    def name(self):
        return self.__device_name

class QUsb2Snes():
    def __init__(self, hostname, port):
        self.__reconnecting = False
        self.__attached_device_name = None
        self.__url = f"ws://{hostname}:{port}"
        self.__lock = asyncio.Lock()
        self.__ws = None
        
    def __command(self, opcode, operands=None):
        data = {
            "Opcode" : opcode,
            "Space" : "SNES"
        }
        if operands:
            data['Operands'] = operands
            
        return json.dumps(data)
        
    async def reconnect_to_device(self):
        if self.__reconnecting:
            await self.connect()
            device = await self.attach_to_device(self.__attached_device_name)
            
            if device:
                print("Connection to device restored.")
                self.__reconnecting = False
        
    async def reconnect(self):
        if not self.__reconnecting and self.__attached_device_name:
            if self.__ws:
                await self.__ws.close()
                self.__ws = None
            print(f"Lost connection to {self.__attached_device_name}. Reconnecting...")
            self.__reconnecting = True
            
    def is_disconnected(self):
        return self.__reconnecting
        
    async def connect(self):
        if self.__ws:
            await self.__ws.close()
            self.__ws = None
            
        self.__ws = await websockets.connect(self.__url)
        
    async def send(self, data):
        try:
            await self.__ws.send(data)
            return True
        except:
            await self.reconnect()
            return False
            
    async def read(self):
        try:
            d = await asyncio.wait_for(self.__ws.recv(), timeout=5.0)
            return d
        except:
            await self.reconnect()
            return None
        
    async def get_devices(self):
        async with self.__lock:
            data = ""
            await self.send(self.__command("DeviceList"))
            data = await self.read()
            try:
                return json.loads(data)
            except:
                print("Failed to parse devices:")
                print(data)
                return {'Results': []}
    
    async def attach_to_device(self, device):
        try:
            async with self.__lock:
                # try to attach
                await self.send(self.__command("Attach", [device]))
                # since it sends no response on success, we have to verify
                await self.send(self.__command("Info", [device]))
                response = json.loads(await self.read())['Results']
                
            self.__attached_device_name = device
            
            return SnesDevice(self, device)
            
        except:
            pass
            
        return None
    
    def __unpack(self, data, size):
        is_power_of_2 = (size & (size - 1) == 0) and (size != 0)
        
        if is_power_of_2 and size <= 8:
            char = 'cHIQ'[int(math.log2(size))]
            return struct.unpack('<' + char, data)
        
        return data
        
    def __unpack_batch(self, data, sizes):
        do_unpack_read = True
        unpack_pattern = '<'
        for size in sizes:
            is_power_of_2 = (size & (size - 1) == 0) and (size != 0)
            
            if is_power_of_2 and size <= 8:
                char = 'cHIQ'[int(math.log2(size))]
                unpack_pattern = unpack_pattern + 'cHIQ'[int(math.log2(size))]
            else:
                do_unpack_read = False
        if do_unpack_read:
            return list(struct.unpack(unpack_pattern, data))
            
        return data
    
    async def read_wram(self, addr, size):
        async with self.__lock:
            await self.send(self.__command("GetAddress", [hex(addr)[2:], hex(size)[2:]]))
            r = await self.read()
            
        if r:
            return self.__unpack(r, size)[0]
            
        return None
        
    async def read_wram_raw(self, addr, size):
        async with self.__lock:
            await self.send(self.__command("GetAddress", [hex(addr)[2:], hex(size)[2:]]))
            return await self.read()
            
    async def read_wram_batch(self, addr_and_sizes):
        results = []
        if not self.is_disconnected():
            async with self.__lock:
                to_send = []
                num_req_bytes = 0
                for addr, size in addr_and_sizes:
                    if num_req_bytes + size <= 64:
                        num_req_bytes += size
                        to_send.append((addr, size))
                        continue
                    addr_size_list = [hex(item)[2:] for pair in to_send for item in pair]
                    await self.send(self.__command("GetAddress", addr_size_list))
                    r = await self.read()
                    
                    if r:
                        results = results + self.__unpack_batch(r, list(zip(*to_send))[1])
                    
                    num_req_bytes = size
                    to_send = [(addr, size)]
                    
                if num_req_bytes:
                    addr_size_list = [hex(item)[2:] for pair in to_send for item in pair]
                    await self.send(self.__command("GetAddress", addr_size_list))
                    r = b''
                    while len(r) < num_req_bytes:
                        r += await self.read()
                    if r:
                        results = results + self.__unpack_batch(r, list(zip(*to_send))[1])
                
        return results