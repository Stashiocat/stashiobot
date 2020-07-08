import threading
import time
import collections
from utils.retroarch import RetroarchReader

# Ram addresses from https://jathys.zophar.net/supermetroid/kejardon/RAMMap.txt

class SuperMetroid():
    def __init__(self):
        self.retroarch_reader = RetroarchReader()
        self.__retroarch_ready = self.retroarch_reader.open_process()
        
        self.__shouldTick = False
        self.__thread = None
        self.__update_rate = 1.0
        
        self.__callback_run_started = None
        self.__callback_run_reset = None
        # TODO: more generic way to subscribe to any room
        self.__callback_enter_moat = None
        self.__callback_enter_phantoon = None
        
        self.__prev_game_info = None
        
    def __del__(self):
        self.retroarch_reader.close_process()
        
    def start_game_info_update(self, update_rate=1.0):
        if self.__retroarch_ready == False:
            print('Failed to start SM reader. Is Retroarch running?')
            return
            
        assert self.__shouldTick == False, "Ticking already started"
        self.__shouldTick = True
        self.__update_rate = update_rate
        self.__thread = threading.Thread(target=self.__tick_update_game_info)
        self.__thread.start()
        
    def stop_game_info_update(self):
        assert self.__shouldTick == True, "Ticking hasn't started yet"
        self.__shouldTick = False
        self.__thread.join()
        self.__thread = None
        
    def subscribe_for_run_start(self, in_callback):
        self.__callback_run_started = in_callback
        
    def subscribe_for_run_reset(self, in_callback):
        self.__callback_run_reset = in_callback
        
    def subscribe_for_enter_moat(self, in_callback):
        self.__callback_enter_moat = in_callback
        
    def subscribe_for_enter_phantoon(self, in_callback):
        self.__callback_enter_phantoon = in_callback
        
    def __tick_update_game_info(self):
        while self.__shouldTick:
            # do update
            new_info = dict()
            new_info['room_id'] = self.__get_room_id()
            new_info['game_state'] = self.__get_game_state()
            
            # do checks
            if self.__callback_run_started and self.__is_new_run_started(new_info):
                self.__callback_run_started()
            elif self.__callback_run_reset and self.__is_run_reset(new_info):
                self.__callback_run_reset()
            elif self.__callback_enter_moat and self.__is_in_moat(new_info):
                self.__callback_enter_moat()
            elif self.__callback_enter_phantoon and self.__is_entering_phantoon_fight(new_info):
                self.__callback_enter_phantoon()

            # set this as our prev info now for next frame
            self.__prev_game_info = new_info
            
            time.sleep(self.__update_rate)
            
    def __is_new_run_started(self, new_info):
        if self.__prev_game_info and new_info:
            if self.__prev_game_info['game_state'] == 0x2: # menu
                if new_info['game_state'] == 0x1F: # it changes to this when the game starts
                    return new_info['room_id'] == 0xDF45 # ceres elevator room
        return False
        
    def __is_run_reset(self, new_info):
        if self.__prev_game_info and new_info:
            if self.__prev_game_info['room_id'] != 0x0:
                if self.__prev_game_info['game_state'] & 0x20 == 0: # attract screen
                    if new_info['room_id'] == 0x0: # room id is 0 after a reset
                        return True
        return False
        
    def __is_in_moat(self, new_info):
        if self.__prev_game_info and new_info:
            if self.__prev_game_info['room_id'] == 0x0948C: # kihunter/crab room before moat
                return new_info['room_id'] == 0x95FF # moat room
        return False
        
    def __is_entering_phantoon_fight(self, new_info):
        if self.__prev_game_info and new_info:
            if self.__prev_game_info['room_id'] == 0xCC6F: # basement room before phantoon
                return new_info['room_id'] == 0xCD13 # phantoon's room
        return False
        
    def __get_room_id(self):
        return self.retroarch_reader.read_short(0x079b)
        
    def __get_game_state(self):
        return self.retroarch_reader.read_short(0x0998)