#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""The engine core holds the entry point into the game execution."""

import collections
import logging
import time

import sdl2
import sdl2.video
import sdl2.ext
import attr
from attr.validators import instance_of

from .entities import Project, World, TextureSpriteRenderSystem


@attr.s
class Engine(object):
    """
    The engine manages the execution of a particular game environment.
    """
    _project = attr.ib(validator=instance_of(Project))
    _debug = attr.ib(default=False, validator=instance_of(bool))
    _log = attr.ib(default=logging.getLogger(__name__), validator=instance_of(logging.Logger), repr=False)

    def run(self):
        """
        Run the engine.

        1. Create the context
        2. Execute within the context
        3. Tear down the context

        :return:
        """
        context = dict()
        try:
            context = self._initialize()
            self._loop(context)
        finally:
            self._teardown(context)

    def _initialize(self):
        """
        Initialize the engine context.

        1. Initialise SDL2
        2. Create the resource database based on RESOURCE_DIR in generic.py
        3. Create and show the window based on WINDOW_TITLE and WINDOW_SHAPE in generic.py
        4. Create the renderer based on WINDOW_SHAPE and CLEAR_COLOR in generic.py
        5. Create the world (using UpdateRenderWorld instead of sdl2.ext.World)
        6. Create the sprite factory
        7. Create custom systems and then the render system
        8. Add all systems to the world in order of creation
        9. Create and add custom entities to the world

        :return:
        """
        self._nfo("Initializing all components of the project.")
        ctx = dict()

        self._dbg("Initializing SDL2.")
        sdl2.ext.init()

        self._dbg("Creating the resource manager.")
        ctx["resources"] = sdl2.ext.Resources(self._project.configuration["resource_path"])

        self._dbg("Creating the window.")
        ctx["window"] = sdl2.ext.Window(
            self._project.configuration["window_title"],
            self._project.configuration["window_shape"],
            flags=self._project.configuration["window_flags"]
        )

        self._dbg("Creating the renderer.")
        sdl2.SDL_SetHint(sdl2.SDL_HINT_RENDER_SCALE_QUALITY, self._project.configuration["render_scale_quality"])
        ctx["renderer"] = sdl2.ext.Renderer(ctx["window"])
        sdl2.SDL_RenderSetLogicalSize(ctx["renderer"].renderer, *self._project.configuration["window_shape"])
        ctx["renderer"].color = sdl2.ext.Color(*self._project.configuration["render_color"])

        self._dbg("Creating the world.")
        ctx["world"] = World()

        self._dbg("Creating the sprite factory.")
        ctx["factory"] = sdl2.ext.SpriteFactory(sdl2.ext.TEXTURE, renderer=ctx["renderer"])

        self._dbg("Creating the EBS systems.")
        ctx["systems"] = collections.OrderedDict()
        ctx["systems"].update(self._project.create_systems())
        ctx["systems"]["render_system"] = TextureSpriteRenderSystem.create(ctx["renderer"])

        self._dbg("Adding systems to the world.")
        for system in ctx["systems"].values():
            ctx["world"].add_system(system)

        if "render_system" in ctx["systems"] and len(ctx["systems"]) == 1:
            self._wrn("Only the render system is present in the world.")
        elif "render_system" not in ctx["systems"]:
            raise RuntimeError("Cannot run the engine without a valid render system.")

        self._dbg("Creating the EBS entities.")
        ctx["entities"] = list()
        ctx["entities"].extend(self._project.create_entities())

        if len(ctx["entities"]) == 0:
            self._wrn("No entities are present in the world.")

        return ctx

    def _teardown(self, ctx):
        """
        Tear down the engine context.

        :param ctx:
        :return:
        """
        # Close down and clean up SDL2
        self._nfo("Closing down SDL2.")
        sdl2.ext.quit()

    def _loop(self, ctx):
        """
        Enter the fixed time-step loop of the game.

        The loop makes sure that the physics update is called at regular intervals based on DELTA_TIME
        from generic.py. The renderer is called when enough simulation intervals have accumulated
        to let it take its time even on slow computers without jeopardizing the physics simulation.
        The maximum duration of a frame is set to FRAME_TIME_MAX in generic.py.

        :param ctx:
        :return:
        """
        self._nfo("Executing within the engine context.")

        # Eliminate as much lookup as possible during the game loop
        renderer = ctx["renderer"]
        world = ctx["world"]
        monotonic = time.monotonic
        min_fun = min
        delta_time = self._project.configuration["delta_time"]
        max_frame_duration = self._project.configuration["max_frame_duration"]
        epsilon = self._project.configuration["epsilon"]

        # Define the time for the event loop
        t = 0.0
        current_time = monotonic()
        accumulator = 0.0

        # Create and run the event loop
        running = True
        while running:
            # Determine how much time we have to perform the physics
            # simulation.
            new_time = monotonic()
            frame_time = new_time - current_time
            current_time = new_time
            frame_time = min_fun(frame_time, max_frame_duration)
            accumulator += frame_time

            # Run the game update until we have one DELTA_TIME left for the
            # rendering step.
            while accumulator >= delta_time:
                # Process SDL events
                events = sdl2.ext.get_events()
                for event in events:
                    if event.type == sdl2.SDL_QUIT:
                        running = False
                        break
                    else:
                        world.dispatch(event)

                world.update(t, delta_time)
                t += delta_time
                accumulator -= delta_time

            # Clear the screen and render the world.
            renderer.clear()
            world.render()

    def _dbg(self, message):
        """
        Send a debug message.

        :param message:
        :return:
        """
        self._log.debug(message)

    def _nfo(self, message):
        """
        Send an info message.

        :param message:
        :return:
        """
        self._log.info(message)

    def _wrn(self, message):
        """
        Send a warning message.

        :param message:
        :return:
        """
        self._log.warn(message)
