import time
import asyncio
import json
from dataclasses import dataclass
from typing import Any, Callable
from utils.supermetroid import SuperMetroid, Rooms, PhantoonPatterns, GameStates

@dataclass
class SuperMetroidCallbacks():
    run_started        : Callable[[], Any]
    run_reset          : Callable[[], Any]
    enter_phantoon     : Callable[[], Any]
    enter_moat         : Callable[[], Any]
    phantoon_fight_end : Callable[[], Any]
    samus_dead         : Callable[[], Any]
    ceres_start        : Callable[[], Any]
    ceres_end          : Callable[[], Any]
    ceres_timer        : Callable[[], Any]
    
class SuperMetroidRun():
    def __init__(self):
        pass
        
    def __del__(self):
        pass
        
class SuperMetroidStats():
    def __init__(self):
        # in the future, it may be worthwhile to move this to a database
        self.__stats_file = 'stats.json'
        self.__stat_json = None
        pass
        
    def __load_stats(self):
        with open(self.__stats_file, 'r') as f:
            self.__stat_json = json.loads(f)

class SuperMetroidRunManager():
    class CeresState():
        NotInCeres = 0
        Intro = 1
        Escape = 2
        
    def __init__(self, in_callbacks):
        self.__sm = SuperMetroid()
        self.__callbacks = in_callbacks
        
        # Internal subscriptions
        self.__sm.subscribe(SuperMetroid.Callbacks.RunStarted , self.__run_started)
        self.__sm.subscribe(SuperMetroid.Callbacks.RunReset   , self.__run_reset)
        self.__sm.subscribe(SuperMetroid.Callbacks.EnemyHP    , self.__enemy_hp)
        self.__sm.subscribe(SuperMetroid.Callbacks.SamusHP    , self.__samus_hp)
        self.__sm.subscribe(SuperMetroid.Callbacks.PhantoonEye, self.__phantoon_eye_timer)
        self.__sm.subscribe(SuperMetroid.Callbacks.CeresTimer , self.__ceres_timer)
        self.__sm.subscribe(SuperMetroid.Callbacks.GameState  , self.__game_state)
        self.__sm.subscribe_to_room_transition(Rooms.WreckedShip.Basement, Rooms.WreckedShip.Phantoon, self.__enter_phantoon)
        self.__sm.subscribe_to_room_transition(Rooms.Crateria.Kihunter   , Rooms.Crateria.Moat       , self.__enter_moat)
        
        self.__in_run = False
        
        # Ceres
        self.__ceres_state = SuperMetroidRunManager.CeresState.NotInCeres
        
        # Phantoon
        self.__in_phantoon_room = False
        self.__in_phantoon_fight = False
        self.__phantoon_dead = False
        self.__current_phantoon_round = 0
        self.__phantoon_patterns = []
            
    def enable_threads(self, loop):
        return self.__sm.enable_threads(loop)
        
    ###########################################################################
    # Internal private callbacks
    ###########################################################################
    async def __run_started(self):
        self.__begin_new_run()
        
    async def __run_reset(self):
        self.__in_run = False
        if self.__ceres_state == SuperMetroidRunManager.CeresState.Escape:
            self.__ceres_state = SuperMetroidRunManager.CeresState.NotInCeres
            
        if self.__callbacks.run_reset:
            self.__callbacks.run_reset()
            
    async def __game_state(self, game_state):
        pass
        
    async def __enter_phantoon(self):
        if self.__in_run and not self.__phantoon_dead:
            self.__in_phantoon_room = True
        
    async def __enter_moat(self):
        if self.__in_run and not self.__phantoon_dead:
            if self.__callbacks.enter_moat:
                self.__callbacks.enter_moat()
            
    async def __enemy_hp(self, hp):
        if self.__in_phantoon_room:
            if not self.__in_phantoon_fight:
                if hp != 0:
                    self.__in_phantoon_fight = True
                    self.__current_phantoon_round = 1
                    self.__phantoon_patterns = []
            else:
                if hp == 0:
                    self.__in_phantoon_fight = False
                    self.__in_phantoon_room = False
                    if self.__callbacks.phantoon_fight_end:
                        self.__callbacks.phantoon_fight_end(self.__phantoon_patterns)
                elif len(self.__phantoon_patterns) == self.__current_phantoon_round:
                    self.__current_phantoon_round += 1
            
    async def __samus_hp(self, hp):
        if hp == 0 and self.__in_run:
            if self.__callbacks.samus_dead:
                self.__callbacks.samus_dead()
            if self.__in_phantoon_fight:
                self.__in_phantoon_fight = False
                self.__in_phantoon_room = False
                self.__phantoon_dead = True
                self.__phantoon_patterns = []
                if self.__callbacks.phantoon_fight_end:
                    self.__callbacks.phantoon_fight_end(['death'])
    
    async def __phantoon_eye_timer(self, timer):
        if self.__in_phantoon_fight:
            if len(self.__phantoon_patterns) < self.__current_phantoon_round:
                pattern = self.__get_phantoon_pattern(timer)
                self.__phantoon_patterns.append(pattern)
                if len(self.__phantoon_patterns) == 1:
                    if self.__callbacks.enter_phantoon:
                        self.__callbacks.enter_phantoon()

    async def __ceres_timer(self, time, is_final):
        if self.__ceres_state == SuperMetroidRunManager.CeresState.Escape and is_final and self.__callbacks.ceres_timer:
            self.__callbacks.ceres_timer(time)
            self.__sm.unsubscribe_to_memory_update(SuperMetroid.MemoryUpdates.Ceres, self.__ceres_update)
            self.__ceres_state = SuperMetroidRunManager.CeresState.NotInCeres
            

    ###########################################################################
    # Private helper functions
    ###########################################################################
    def __get_phantoon_pattern(self, timer):
        if timer <= PhantoonPatterns.Fast:
            return 'fast'
        elif timer <= PhantoonPatterns.Mid:
            return 'mid'
            
        return 'slow'
            
    async def __ceres_update(self, ceres_data):
        if self.__ceres_state == SuperMetroidRunManager.CeresState.Intro and ceres_data['ceres_state'] == SuperMetroidRunManager.CeresState.Escape:
            self.__ceres_state = SuperMetroidRunManager.CeresState.Escape
            if self.__callbacks.ceres_end:
                self.__callbacks.ceres_end()
                
    def __begin_new_run(self):
        # Reset state
        self.__in_run = True
        self.__in_phantoon_room = False
        self.__in_phantoon_fight = False
        self.__phantoon_dead = False
        self.__current_phantoon_round = 0
        self.__phantoon_patterns = []
        self.__in_run = True
        
        if self.__callbacks.ceres_timer:
            self.__sm.subscribe_to_memory_update(SuperMetroid.MemoryUpdates.Ceres, self.__ceres_update)
        
        if self.__callbacks.ceres_start and self.__ceres_state is not SuperMetroidRunManager.CeresState.Intro:
            self.__callbacks.ceres_start()
            self.__ceres_state = SuperMetroidRunManager.CeresState.Intro
        
        if self.__callbacks.run_started:
            self.__callbacks.run_started()