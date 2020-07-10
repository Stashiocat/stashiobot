import threading
import time
import collections
from utils.retroarch import RetroarchReader

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
        Kihunter = 0x948C
        Moat     = 0x95FF
        
    class WreckedShip():
        Basement = 0xCC6F
        Phantoon = 0xCD13

class WRamOffsets():
    RoomID               = 0x079B
    GameState            = 0x0998
    EnemyHP              = 0x0F8C
    PhantoonEyeOpenTimer = 0x0FE8

class SuperMetroid():
    def __init__(self):
        self.retroarch_reader = RetroarchReader()
        self.__retroarch_ready = self.retroarch_reader.open_process()
        
        self.__shouldTick = False
        self.__thread = None
        self.__update_rate = 1.0
        
        self.__callback_run_started = None
        self.__callback_run_reset = None
        self.__room_transition_callbacks = []
        
        self.__prev_game_info = None
        
    def __del__(self):
        self.retroarch_reader.close_process()
        
    def start_game_info_update(self, update_rate=1.0):
        if self.__retroarch_ready == False:
            # todo: create a thread that waits for retroarch to run
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
        
    def subscribe_to_room_transition(self, before, after, in_callback):
        data = {
            'from': before,
            'to': after,
            'callback': in_callback
        }
        self.__room_transition_callbacks.append(data)
        
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
            elif self.__prev_game_info != None:
                for transition in self.__room_transition_callbacks:
                    if self.__check_room_transition(new_info, transition['from'], transition['to']):
                        transition['callback']()

            # set this as our prev info now for next frame
            self.__prev_game_info = new_info
            
            time.sleep(self.__update_rate)
            
    def __is_new_run_started(self, new_info):
        if self.__prev_game_info and new_info:
            return self.__check_game_transition(new_info, GameStates.GameOptionsMenu, GameStates.NewGamePostIntro)
        return False
        
    def __is_run_reset(self, new_info):
        if self.__prev_game_info and new_info:
            if self.__prev_game_info['room_id'] != Rooms.Empty:
                if new_info['room_id'] == Rooms.Empty:
                    return GameStates.is_demo_state(self.__prev_game_info['game_state']) == False
                    
        return False
    
    def __check_room_transition(self, new_game_info, before, after):
        return self.__prev_game_info['room_id'] == before and new_game_info['room_id'] == after
        
    def __check_game_transition(self, new_game_info, before, after):
        return self.__prev_game_info['game_state'] == before and new_game_info['game_state'] == after
    
    def __get_room_id(self):
        return self.retroarch_reader.read_short(WRamOffsets.RoomID)
        
    def __get_game_state(self):
        return self.retroarch_reader.read_short(WRamOffsets.GameState)