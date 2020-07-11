import time
import threading
from dataclasses import dataclass
from typing import Any, Callable
from utils.supermetroid import SuperMetroid, Rooms, PhantoonPatterns

@dataclass
class SuperMetroidCallbacks():
    run_started        : Callable[[], Any]
    run_reset          : Callable[[], Any]
    enter_phantoon     : Callable[[], Any]
    enter_moat         : Callable[[], Any]
    phantoon_fight_end : Callable[[], Any]
    samus_dead         : Callable[[], Any]
    

class SuperMetroidRunManager():
    def __init__(self, in_callbacks):
        self.__sm = SuperMetroid()
        self.__sm.start_game_info_update(1.0/60.0)

        self.__callbacks = in_callbacks
        
        # Internal subscriptions
        self.__sm.subscribe_for_run_start(self.__run_started)
        self.__sm.subscribe_for_run_reset(self.__run_reset)
        self.__sm.subscribe_to_room_transition(Rooms.WreckedShip.Basement, Rooms.WreckedShip.Phantoon, self.__enter_phantoon)
        self.__sm.subscribe_to_room_transition(Rooms.Crateria.Kihunter, Rooms.Crateria.Moat, self.__enter_moat)
        self.__sm.subscribe_to_enemy_hp(self.__enemy_hp)
        self.__sm.subscribe_to_samus_hp(self.__samus_hp)
        self.__sm.subscribe_to_phantoon_eye(self.__phantoon_eye_timer)
        
        self.__in_run = True
        self.__in_phantoon_room = False
        self.__in_phantoon_fight = False
        self.__current_phantoon_round = 0
        self.__phantoon_patterns = []
        
    ###########################################################################
    # Internal private callbacks
    ###########################################################################
    def __run_started(self):
        self.__in_run = True
        if self.__callbacks.run_started:
            self.__callbacks.run_started()
        
    def __run_reset(self):
        self.__in_run = False
        if self.__callbacks.run_reset:
            self.__callbacks.run_reset()
        
    def __enter_phantoon(self):
        if self.__in_run:
            self.__in_phantoon_room = True
            if self.__callbacks.enter_phantoon:
                self.__callbacks.enter_phantoon()
        
    def __enter_moat(self):
        if self.__in_run and self.__callbacks.enter_moat:
            self.__callbacks.enter_moat()
            
    def __enemy_hp(self, hp):
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
            
    def __samus_hp(self, hp):
        if hp == 0 and self.__in_run:
            if self.__callbacks.samus_dead:
                self.__callbacks.samus_dead()
            if self.__in_phantoon_fight:
                self.__in_phantoon_fight = False
                self.__in_phantoon_room = False
                self.__phantoon_patterns = []
                if self.__callbacks.phantoon_fight_end:
                    self.__callbacks.phantoon_fight_end(['death'])
    
    def __phantoon_eye_timer(self, timer):
        if self.__in_phantoon_fight:
            if len(self.__phantoon_patterns) < self.__current_phantoon_round:
                pattern = self.__get_phantoon_pattern(timer)
                print('Phantoon pattern:', pattern)
                self.__phantoon_patterns.append(pattern)

    ###########################################################################
    # Private helper functions
    ###########################################################################
    def __get_phantoon_pattern(self, timer):
        if timer <= PhantoonPatterns.Fast:
            return 'fast'
        elif timer <= PhantoonPatterns.Mid:
            return 'mid'
            
        return 'slow'
            
    