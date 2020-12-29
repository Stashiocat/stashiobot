import threading
import time
import collections
from utils.retroarch import RetroarchReader, ErrorReadingMemoryException

# Info taken from several places
# 1. https://jathys.zophar.net/supermetroid/kejardon/
# 2. http://patrickjohnston.org/ASM/ROM%20data/Super%20Metroid/
# 3. Cheat engine

class GameStates():
    Start                   = 0x00 # Reset/start
    OpeningCinematic        = 0x01 # Opening. Cinematic
    GameOptionsMenu         = 0x02 # Game options menu
    Nothing                 = 0x03 # Nothing (RTS)
    SaveGameMenu            = 0x04 # Save game menus
    LoadingGameMapView      = 0x05 # Loading game map view
    LoadingGameData         = 0x06 # Loading game data
    InitGameAfterLoad       = 0x07 # Setting game up after loading the game
    Gameplay                = 0x08 # Main gameplay
    HitDoorBlock            = 0x09 # Hit a door block
    LoadNextRoom            = 0x0A # Loading next room
    LoadNextRoom2           = 0x0B # Loading next room
    FadeToPause             = 0x0C # Pausing, normal gameplay but darkening
    LoadPauseScreen         = 0x0D # Pausing, loading pause screen
    LoadPauseScreen2        = 0x0E # Paused, loading pause screen
    Paused                  = 0x0F # Paused, map and item screens
    Unpausing               = 0x10 # Unpausing, loading normal gameplay
    Unpausing2              = 0x11 # Unpausing, loading normal gameplay
    FadeFromPause           = 0x12 # Unpausing, normal gameplay but brightening
    SamusDead               = 0x13 # Samus ran out of health
    SamusDeadBlackOut       = 0x14 # Samus ran out of health, black out surroundings
    SamusDeadBlackOut2      = 0x15 # Samus ran out of health, black out surroundings
    SamusDeadBeginDeathAni  = 0x16 # Samus ran out of health, starting death animation
    SamusDeadFlashing       = 0x17 # Samus ran out of health, flashing
    SamusDeadExplosion      = 0x18 # Samus ran out of health, explosion
    SamusDeadFadeToBlack    = 0x19 # Samus ran out of health, black out (also cut to by time up death)
    GameOver                = 0x1A # Game over screen
    AutoReserve             = 0x1B # Reserve tanks auto
    Unused                  = 0x1C # Unused. Does JMP ($0DEA) ($0DEA is also unused)
    DebugMenu               = 0x1D # Debug menu (end/continue)
    IntroCinematic          = 0x1E # Intro. Cinematic. Set up entirely new game with cutscenes
    NewGamePostIntro        = 0x1F # Set up new game. Post-intro
    CeresElevator           = 0x20 # Made it to Ceres elevator
    BlackoutFromCeres       = 0x21 # Blackout from Ceres
    CeresDestroyedCinematic = 0x22 # Ceres goes boom, Samus goes to Zebes. Cinematic
    CeresTimeUp             = 0x23 # Time up
    TimeUpFadeToWhite       = 0x24 # Whiting out from time up
    CeresDestroyedWithSamus = 0x25 # Ceres goes boom with Samus. Cinematic
    BeatTheGame             = 0x26 # Samus escapes from Zebes. Transition from main gameplay to ending and credits
    EndCreditsCinematic     = 0x27 # Ending and credits. Cinematic
    TransitionToDemo        = 0x28 # Transition to demo
    TransitionToDemo2       = 0x29 # Transition to demo
    PlayingDemo             = 0x2A # Playing demo
    TransitionFromDemo      = 0x2B # Transition from demo
    TransitionFromDemo2     = 0x2C # Transition from demo
    
    def is_demo_state(state):
        demoStates = [
            GameStates.TransitionToDemo,
            GameStates.TransitionToDemo2,
            GameStates.PlayingDemo,
            GameStates.TransitionFromDemo,
            GameStates.TransitionFromDemo2
        ]
        return any([state == s for s in demoStates])

class Rooms():
    Empty = 0x0000
    class Ceres():
        Elevator = 0xDF45
        
    class Crateria():
        Kihunter            = 0x948C
        Moat                = 0x95FF
        RedBrinstarElevator = 0x962A
        
    class RedBrinstar():
        Caterpillar = 0xA322
        
    class WreckedShip():
        Basement = 0xCC6F
        Phantoon = 0xCD13
    
class PhantoonPatterns():
    Fast = 0x003C
    Mid  = 0x0168
    Slow = 0x02D0
    
class CeresEscapeState():
    NotInEscape          = 0x0000
    RidleySwoopCutscene  = 0x0001
    EscapeTimerInitiated = 0x0002
    ElevatorRoomRotating = 0x8000

class SuperMetroid():
    class Callbacks():
        RunStarted  = 0
        RunReset    = 1
        EnemyHP     = 2
        SamusHP     = 3
        PhantoonEye = 4
        CeresTimer  = 5
        GameState   = 6
        
    class MemoryUpdates():
        Ceres = 0
        
    def __init__(self):        
        self.__update_game_thread = None
        self.__hook_retroarch_thread = None
        
        self.__shouldTick = False
        self.__update_rate = 1.0
        
        self.__callbacks = dict()
        self.__room_transition_callbacks = []
        self.__current_subscriptions = []
        
        self.__prev_game_info = None

        self.retroarch_reader = RetroarchReader()
        self.__retroarch_ready = self.retroarch_reader.open_process()
        
        if not self.__retroarch_ready:
            print('Failed to hook snes9x_libretro.dll in retroarch.exe. Waiting for process.')
            self.__hook_retroarch_thread = threading.Thread(target=self.__tick_hook_retroarch)
            self.__hook_retroarch_thread.start()
        else:
            print('Retroarch hooked!')

        self.__wram_offsets = {
            'always_update': {
                'room_id'   : { 'offset': 0x079B, 'size': 2 },
                'game_state': { 'offset': 0x0998, 'size': 2 },
                'samus_hp'  : { 'offset': 0x09C2, 'size': 2 },
            },
            # Memory address to read if you're in a specific room
            'room_update': {
                Rooms.WreckedShip.Phantoon: {
                    'enemy_hp'           : { 'offset': 0x0F8C, 'size': 2 },
                    'phantoon_eye_timer' : { 'offset': 0x0FE8, 'size': 2 },
                }
            },
            # Allow subscribing to read certain values
            'subscriptions': {
                SuperMetroid.MemoryUpdates.Ceres: {
                    'ceres_timer': { 'offset': 0x945, 'size': 2 },
                    'ceres_state': { 'offset': 0x93F, 'size': 2 },
                }
            }
        }
        
        self.__callback_info = {
            # Subscription ID                         # Check if callback should be called      # Parameters for the callback
            SuperMetroid.Callbacks.RunStarted:  { 'check': self.__is_new_run_started,       'params': lambda info: [], },
            SuperMetroid.Callbacks.RunReset:    { 'check': self.__is_run_reset,             'params': lambda info: [], },
            SuperMetroid.Callbacks.EnemyHP:     { 'check': self.__check_enemy_hp_change,    'params': lambda info: [info['enemy_hp']], },
            SuperMetroid.Callbacks.SamusHP:     { 'check': self.__check_samus_hp_change,    'params': lambda info: [info['samus_hp']], },
            SuperMetroid.Callbacks.PhantoonEye: { 'check': self.__check_phantoon_eye_timer, 'params': lambda info: [info['phantoon_eye_timer']], },
            SuperMetroid.Callbacks.CeresTimer:  { 'check': self.__check_ceres_timer,        'params': lambda info: [info['ceres_timer'], info['game_state'] == GameStates.CeresDestroyedCinematic], },
            SuperMetroid.Callbacks.GameState:   { 'check': self.__check_game_state,         'params': lambda info: [info['game_state']], },
        }
        
    def __del__(self):
        self.retroarch_reader.close_process()
        
    def start_game_info_update(self, update_rate=1.0):
        assert self.__shouldTick == False, "Ticking already started"
        self.__shouldTick = True
        self.__update_rate = update_rate
        self.__update_game_thread = threading.Thread(target=self.__tick_update_game_info)
        self.__update_game_thread.start()
        
    def stop_game_info_update(self):
        assert self.__shouldTick == True, "Ticking hasn't started yet"
        self.__shouldTick = False
        self.__update_game_thread.join()
        self.__update_game_thread = None
        
    def subscribe(self, in_type, in_callback):
        if not in_type in self.__callbacks:
            self.__callbacks[in_type] = in_callback
        
    def unsubscribe(self, in_type):
        if in_type in self.__callbacks:
            del self.__callbacks[in_type]
            
    def subscribe_to_memory_update(self, in_type, in_callback):
        if not (in_type, in_callback) in self.__current_subscriptions:
            self.__current_subscriptions.append((in_type, in_callback))
            
    def unsubscribe_to_memory_update(self, in_type, in_callback):
        if (in_type, in_callback) in self.__current_subscriptions:
            self.__current_subscriptions.remove((in_type, in_callback))
        
    def subscribe_to_room_transition(self, before, after, in_callback):
        data = {
            'from': before,
            'to': after,
            'callback': in_callback
        }
        self.__room_transition_callbacks.append(data)
        
    def __tick_hook_retroarch(self):
        while not self.__retroarch_ready:
            self.__retroarch_ready = self.retroarch_reader.open_process()
            
            #try every second or so
            time.sleep(1.0)
        print('Connection to Super Metroid restored.')
        self.__hook_retroarch_thread = None
        
    def __tick_update_game_info(self):
        while self.__shouldTick:
            if self.__retroarch_ready:
                new_info = self.__read_updated_memory()
                
                if self.__prev_game_info:
                    for subscription in self.__callbacks:
                        if self.__callbacks[subscription]:
                            ci = self.__callback_info[subscription]
                            if ci['check'](new_info):
                                self.__callbacks[subscription](*ci['params'](new_info))
                
                    for transition in self.__room_transition_callbacks:
                        if self.__check_room_transition(new_info, transition['from'], transition['to']):
                            transition['callback']()

                # set this as our prev info now for next frame
                self.__prev_game_info = new_info
            
            time.sleep(self.__update_rate)
            
    def __is_new_run_started(self, new_info):
        return self.__check_game_transition(new_info, GameStates.GameOptionsMenu, GameStates.NewGamePostIntro)
        
    def __is_run_reset(self, new_info):
        if self.__prev_game_info['room_id'] != Rooms.Empty:
            if new_info['room_id'] == Rooms.Empty:
                return GameStates.is_demo_state(self.__prev_game_info['game_state']) == False
                    
        return False
        
    def __check_property_change(self, prop, new_info):
        return prop in new_info and ((prop not in self.__prev_game_info) or self.__prev_game_info[prop] != new_info[prop])
        
    def __check_enemy_hp_change(self, new_info):
        return self.__check_property_change('enemy_hp', new_info)
        
    def __check_samus_hp_change(self, new_info):
        return self.__check_property_change('samus_hp', new_info)
        
    def __check_game_state(self, new_info):
        return self.__check_property_change('game_state', new_info)
        
    def __check_phantoon_eye_timer(self, new_info):
        return self.__check_property_change('phantoon_eye_timer', new_info)
        
    def __check_ceres_timer(self, new_info):
        is_ceres_cinematic = self.__check_game_transition(new_info, GameStates.BlackoutFromCeres, GameStates.CeresDestroyedCinematic)
        return self.__check_property_change('ceres_timer', new_info) or is_ceres_cinematic
    
    def __check_room_transition(self, new_info, before, after):
        return self.__prev_game_info['room_id'] == before and new_info['room_id'] == after
        
    def __check_game_transition(self, new_info, before, after):
        return self.__prev_game_info['game_state'] == before and new_info['game_state'] == after
    
    def __read_mem(self, addr, size):
        try:
            return self.retroarch_reader.read_memory(addr, size)
        except ErrorReadingMemoryException:
            if not self.__hook_retroarch_thread:
                self.__retroarch_ready = False
                print('Lost connection to Super Metroid. Attempting reconnection.')
                self.__hook_retroarch_thread = threading.Thread(target=self.__tick_hook_retroarch)
                self.__hook_retroarch_thread.start()
                
        return None
        
    def __read_updated_memory(self):
        mem = dict()
        for field in self.__wram_offsets['always_update']:
            assert field not in mem, f"'{field}' already present in __wram_offsets"
            info = self.__wram_offsets['always_update'][field]
            mem[field] = self.__read_mem(info['offset'], info['size'])
            
        assert 'room_id' in mem, "'room_id' must be present under 'always_update' in __wram_offsets!"
        
        # Check if there's any addresses we want to read if we're in this specific room
        if mem['room_id'] in self.__wram_offsets['room_update']:
            room_info = self.__wram_offsets['room_update'][mem['room_id']]
            for field in room_info:
                assert field not in mem, f"'{field}' already present in __wram_offsets"
                info = room_info[field]
                mem[field] = self.__read_mem(info['offset'], info['size'])
                
        for sub, sub_callback in self.__current_subscriptions:
            if sub in self.__wram_offsets['subscriptions']:
                sub_info = self.__wram_offsets['subscriptions'][sub]
                cb_mem = {}
                for mem_name in sub_info:
                    cb_mem[mem_name] = self.__read_mem(sub_info[mem_name]['offset'], sub_info[mem_name]['size'])
                    mem[mem_name] = cb_mem[mem_name]
                sub_callback(cb_mem)
                
        return mem
        