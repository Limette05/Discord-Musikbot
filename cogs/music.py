from youtubesearchpython.__future__ import *

import datetime
import time
import re
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

import random
import yt_dlp
import validators
import nextcord
import asyncio
from nextcord import Interaction, SlashOption
from nextcord.ext import commands
from nextcord.ui import *
from pytube import Playlist


class music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # spotify
        self.spotify_id = 'your_spotify_id'
        self.spotify_secret = 'your_spotify_secret'
        self.spotify_redirect_uri = 'http://your_url/callback'  # Deine Redirect URI

        self.is_loading = {}

        self.auth_manager = SpotifyClientCredentials(client_id=self.spotify_id,
                                                     client_secret=self.spotify_secret)
        self.sp = spotipy.Spotify(auth_manager=self.auth_manager)

        self.current_positions = {}
        self.last_volume_change = {}
        self.volume_change = {}
        self.custom_volume = {}
        self.guilds = []
        self.vc = {}
        self.voice_channel = {}
        self.loop = {}
        self.shuffle = {}
        self.shuffled = {}
        self.unshuffled_queue = {}
        self.position = {}
        self.queue = {}
        self.playlists = {}
        self.playing = {}
        self.song_count = {}
        self.skipped = {}
        self.volume = {}

        self.yt_urls = ["https://youtube", "http://youtube", "https://www.youtube", "http://www.youtube",
                        "https://music.youtube", "http://music.youtube", "https://m.youtube", "http://m.youtube",
                        "https://youtu.be", "http://youtu.be"]
        self.spotify_urls = ["https://open.spotify.com/", "http://open.spotify.com/"]

        self.FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'}
        self.fetcher = StreamURLFetcher()
        self.YDL_OPTIONS = {
            'format': 'bestaudio',
            'noplaylist': 'True'}
        self.ydl = yt_dlp.YoutubeDL(self.YDL_OPTIONS)

    @commands.Cog.listener()
    async def on_ready(self):
        print("music loaded")

    async def check_guild(self, guild):
        if guild not in self.guilds:
            self.guilds.append(guild)
            self.vc[guild] = None
            self.voice_channel[guild] = None
            self.loop[guild] = 0
            self.shuffle[guild] = False
            self.shuffled[guild] = 0
            self.position[guild] = 0
            self.song_count[guild] = 0
            self.queue[guild] = []
            self.playing[guild] = None
            self.skipped[guild] = False

    @commands.Cog.listener()
    async def track_end(self, guild):
        """
        Diese Funktion wird ausgeführt, wenn ein Track beendet wird und verwaltet die Wiedergabeliste,
        das Wiederholen von Tracks und das Verbinden/Trennen von Sprachkanälen.
        """

        if self.vc[guild] is None:
            # Wenn kein Sprachkanal verbunden ist, beende die Funktion.
            return

        if guild in self.volume_change:
            # Wenn die Lautstärke angepasst wurde, beende, die Funktion.
            self.volume_change[guild] = False
            return

        # Prüfe, ob ein einzelner Track wiederholt wird (loop == 1)
        if self.loop[guild] == 1:
            # Extrahiere die URL des aktuellen Tracks
            data = self.ydl.extract_info(self.playing[guild]['url'],
                                         download=False)
            url = data['url']

            # Spiele den Track erneut ab
            self.vc[guild].play(nextcord.FFmpegPCMAudio(url,
                                                        **self.FFMPEG_OPTIONS),
                                after=lambda e: asyncio.run(self.track_end(guild)))
            self.vc[guild].source = nextcord.PCMVolumeTransformer(self.vc[guild].source,
                                                                  volume=self.custom_volume[guild] / 100 * 0.75)

            # Aktualisiere die Startzeit des Tracks
            self.playing[guild]['started'] = datetime.datetime.now()
            return

        # Reduziere die Anzahl der Songs in der Queue
        self.song_count[guild] -= 1

        # Prüfe, ob die Playlist wiederholt wird
        playlistloop = False
        if self.loop[guild] == 2:
            # Stelle die Songanzahl wieder her und setze das Flag für die Playlist-Wiederholung
            self.song_count[guild] += 1
            playlistloop = True

        # Setze das "skipped"-Flag zurück
        if self.skipped[guild]:
            self.skipped[guild] = False

        # Bestimme den nächsten Track
        if self.song_count[guild] >= 2:
            # Aktualisiere die Position innerhalb der Queue (ggf. mit Wrap-around)
            if playlistloop:
                self.position[guild] += 1
                if self.position[guild] >= len(self.queue[guild]):
                    self.position[guild] = 0

        # Bestimme den nächsten Track aus der Queue und aktualisiere die Position
        if self.song_count[guild] == 0:
            return
        self.playing[guild] = self.queue[guild][self.position[guild]]

        # Entferne den aktuellen Track aus der Queue (außer bei Playlist-Wiederholung)
        if not playlistloop:
            self.queue[guild].remove(self.playing[guild])
            if self.shuffle[guild]:
                self.unshuffled_queue[guild].remove(self.playing[guild])

        # Extrahiere die URL des nächsten Tracks
        data = self.ydl.extract_info(self.playing[guild]['url'],
                                     download=False)
        url = data['url']

        # Spiele den nächsten Track ab
        self.vc[guild].play(nextcord.FFmpegPCMAudio(url,
                                                    **self.FFMPEG_OPTIONS),
                            after=lambda e: asyncio.run(self.track_end(guild)))
        self.vc[guild].source = nextcord.PCMVolumeTransformer(self.vc[guild].source,
                                                              volume=self.custom_volume[guild] / 100 * 0.75)

        # Aktualisiere die Startzeit des neuen Tracks
        self.playing[guild]['started'] = datetime.datetime.now()

        # Todo
        #     #  Fehlerhaft, trennt manchmal grundlos verbindung
        #     #  if self.song_count[guild] < 1:
        #     #     while self.vc[guild].is_playing():  # Checks if voice is playing
        #     #         await asyncio.sleep(1)  # While it's playing it sleeps for 1 second
        #     #     else:
        #     #         await asyncio.sleep(300)  # If it's not playing it waits
        #     #         while self.vc[guild].is_playing():  # and checks once again if the bot is not playing
        #     #             break  # if it's playing it breaks
        #     #         else:
        #     #             # if not it disconnects
        #     #             self.vc[guild].cleanup()
        #     #             await self.vc[guild].disconnect(force=True)
        #     #             self.vc[guild] = None
        #     #             self.voice_channel[guild] = None
        #     #             self.loop[guild] = 0
        #     #             self.shuffle[guild] = False
        #     #             self.shuffled[guild] = 0
        #     #             self.position[guild] = 0
        #     #             self.queue[guild] = []
        #     #             self.playing[guild] = None
        #     #             self.song_count[guild] = 0
        #     #             self.skipped[guild] = False
        #     #             return

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: nextcord.Member, before: nextcord.VoiceState,
                                    after: nextcord.VoiceState):

        if member.id != self.bot.user.id:
            return
        if not before.channel:
            print("first join")
            return

        if not after.channel:
            guild = before.channel.guild.id
            print("leave erkannt")
            try:
                await self.vc[guild].disconnect(force=True)
            except Exception as e:
                pass
            try:
                self.vc[guild].cleanup()
            except Exception as e:
                pass
            self.vc[guild] = None
            self.voice_channel[guild] = None
            self.loop[guild] = 0
            self.shuffle[guild] = False
            self.shuffled[guild] = 0
            self.position[guild] = 0
            self.queue[guild] = []
            self.playing[guild] = None
            self.song_count[guild] = 0
            self.skipped[guild] = False
            return
        if before.channel == after.channel:
            print("Server deaf/mute erkannt")
            return

        guild = after.channel.guild.id
        if self.vc[guild] != None:
            self.voice_channel[guild] = after.channel
            await asyncio.sleep(0.5)  # wait a moment for it to set in
            self.vc[guild].pause()
            await asyncio.sleep(0.5)  # wait a moment for it to set in
            self.vc[guild].resume()
            print("Channel gewechselt!")

    @nextcord.slash_command(name="controller",
                            description="Kontrollfeld für den Musikbot")
    async def controller(self, i: Interaction):
        guild = i.guild.id
        await asyncio.create_task(self.check_guild(guild))
        if self.vc[guild] is None:
            return await i.send("Ich bin nicht verbunden! \n>>> `/play [Titel/URL]`",
                                ephemeral=True,
                                delete_after=6)

        con_view = View(timeout=False)
        play = Button(label="Pause/Weiter",
                      style=nextcord.ButtonStyle.green,
                      emoji="⏯")
        stop = Button(label="Stop",
                      style=nextcord.ButtonStyle.red,
                      emoji="⏹")
        skip = Button(label="Skip",
                      style=nextcord.ButtonStyle.grey,
                      emoji="⏭")
        loop = Button(label="Loop",
                      style=nextcord.ButtonStyle.grey,
                      emoji="🔁")
        shuffle = Button(label="Shuffle",
                         style=nextcord.ButtonStyle.grey,
                         emoji="🔀")
        playlist = Button(label="Playlist",
                          style=nextcord.ButtonStyle.blurple,
                          emoji="🎶")
        titel = Button(label="Info",
                       style=nextcord.ButtonStyle.blurple,
                       emoji="ℹ️")

        play.callback = self.playpause
        stop.callback = self.stop
        skip.callback = self.skip
        loop.callback = self.loop_function
        shuffle.callback = self.shuffle_function
        playlist.callback = self.playlist
        titel.callback = self.titel

        con_view.add_item(play)
        con_view.add_item(stop)
        con_view.add_item(skip)
        con_view.add_item(loop)
        con_view.add_item(shuffle)
        con_view.add_item(playlist)
        con_view.add_item(titel)

        await i.send("Kontrollier den Musikbot:",
                     view=con_view,
                     ephemeral=True)

    @commands.Cog.listener()
    async def playpause(self, i: Interaction):
        guild = i.guild.id
        await asyncio.create_task(self.check_guild(guild))
        if not i.guild.voice_client:
            return await i.send("Es lief nie Musik... ¯\_(ツ)_/¯",
                                ephemeral=True,
                                delete_after=5)
        elif not i.user.voice:
            return await i.send("Wir müssen im gleichen Voice-Channel sein!",
                                ephemeral=True,
                                delete_after=5)
        elif self.voice_channel[guild].id != i.user.voice.channel.id:
            return await i.send("Wir müssen im gleichen Voice-Channel sein!",
                                ephemeral=True,
                                delete_after=5)

        if self.vc[guild].is_playing() and not self.vc[guild].is_paused():
            self.vc[guild].pause()
        else:
            self.vc[guild].resume()

    def get_spotify_track_id(self, url):
        # Regex, die alle möglichen Spotify-Track-URL-Varianten erfasst
        match = re.match(r'https?://open\.spotify\.com/(intl-[a-zA-Z]+/)?track/([a-zA-Z0-9]+)',
                         url)
        if match:
            return match.group(2)  # Rückgabe der Track-ID (zweite Gruppe)
        return None

    # ToDo
    #  custom playlists
    #  add url and name to databank

    def get_playlist_tracks(self, playlist_uri):
        results = self.sp.playlist_items(playlist_uri)
        tracks = results['items']
        while results['next']:
            results = self.sp.next(results)
            tracks.extend(results['items'])

        playlist_dict = []
        for track in tracks:
            playlist_dict.append({
                                     'title': track['track']['name'],
                                     'artist': track['track']['artists'][0]['name']})
        return playlist_dict

    async def get_current_position(self, vc, guild):
        while vc.is_playing():
            try:
                elapsed_time = datetime.datetime.now() - self.playing[guild]['started']
                return elapsed_time
            except Exception as e:
                print(f"|{datetime.datetime.utcnow()}| Fehler bei der Abfrage der Position: {e}")

    @nextcord.slash_command(name="volume")
    @commands.cooldown(1,
                       5,
                       commands.BucketType.user)
    async def set_volume(self, i: Interaction, volume: int = SlashOption(description="Lautstärke von 5% bis 100%",
                                                                         min_value=5,
                                                                         max_value=100)):
        guild = i.guild
        self.volume_change[guild.id] = True

        if not self.vc[guild.id] or not self.vc[guild.id].is_playing():
            await i.send("Es läuft gerade kein Track.",
                         ephemeral=True,
                         delete_after=5)
            return
        elif not i.user.voice:
            return await i.send("Wir müssen im gleichen Voice-Channel sein!",
                                ephemeral=True,
                                delete_after=5)
        elif self.voice_channel[guild.id].id != i.user.voice.channel.id:
            return await i.send("Wir müssen im gleichen Voice-Channel sein!",
                                ephemeral=True,
                                delete_after=5)

        if self.custom_volume[guild.id] == volume:
            return await i.send("Die Lautstärke ist bereits eingestellt!.",
                                ephemeral=True,
                                delete_after=5)

        # Überprüfen, ob der Cooldown abgelaufen ist
        if not guild.id in self.last_volume_change:
            pass
        elif time.time() - self.last_volume_change[guild.id] < 5:
            await i.send("Bitte warte 5 Sekunden, bevor du die Lautstärke erneut änderst.",
                         ephemeral=True,
                         delete_after=5)
            return

        # Speichere die aktuelle Position im Track
        current_time = await self.get_current_position(self.vc[guild.id],
                                                       guild.id)

        # Stoppe den aktuellen Track
        self.vc[guild.id].stop()

        # Erstelle die Audioquelle mit der neuen Lautstärke und starte ab der gespeicherten Position
        opts = {
            'before_options': f'-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -ss {str(current_time)}',
            'options': '-vn'}

        self.vc[guild.id].play(nextcord.FFmpegPCMAudio(self.playing[guild.id]['url'],
                                                       **opts),
                               after=lambda e: asyncio.run(self.track_end(guild.id)))
        self.vc[guild.id].source = nextcord.PCMVolumeTransformer(self.vc[guild.id].source,
                                                                 volume=volume / 100 * 0.75)
        self.custom_volume[guild.id] = volume

        # Speichere die neue Lautstärke und aktualisiere den Cooldown-Timer
        self.last_volume_change[guild.id] = time.time()

        await i.send(f"Lautstärke auf {volume}% geändert.",
                     ephemeral=True,
                     delete_after=5)

    @nextcord.slash_command(name="play",
                            description="Ich akzeptiere: YT-Suche/YT-Link/YT-Playlist")
    async def play(self, i: Interaction,
                   search: str = SlashOption(description="Titel/URL")):
        guild = i.guild.id
        await asyncio.create_task(self.check_guild(guild))
        if not i.user.voice:
            return await i.send("Du musst in einem Channel sein!",
                                ephemeral=True,
                                delete_after=5)
        if self.song_count[guild] >= 30:
            return await i.send("Die Warteschlange ist voll!",
                                ephemeral=True,
                                delete_after=5)
        if self.vc[guild] != None:
            if self.voice_channel[guild].id != i.user.voice.channel.id:
                return await i.send("Wir müssen im gleichen Voice-Channel sein!",
                                    ephemeral=True,
                                    delete_after=5)

        con_view = View(timeout=False)
        play = Button(label="Pause/Weiter",
                      style=nextcord.ButtonStyle.green,
                      emoji="⏯")
        stop = Button(label="Stop",
                      style=nextcord.ButtonStyle.red,
                      emoji="⏹")
        skip = Button(label="Skip",
                      style=nextcord.ButtonStyle.grey,
                      emoji="⏭")
        loop = Button(label="Loop",
                      style=nextcord.ButtonStyle.grey,
                      emoji="🔁")
        shuffle = Button(label="Shuffle",
                         style=nextcord.ButtonStyle.grey,
                         emoji="🔀")
        playlistb = Button(label="Playlist",
                           style=nextcord.ButtonStyle.blurple,
                           emoji="🎶")
        titel = Button(label="Info",
                       style=nextcord.ButtonStyle.blurple,
                       emoji="ℹ️")

        play.callback = self.playpause
        stop.callback = self.stop
        skip.callback = self.skip
        loop.callback = self.loop_function
        shuffle.callback = self.shuffle_function
        playlistb.callback = self.playlist
        titel.callback = self.titel

        con_view.add_item(play)
        con_view.add_item(stop)
        con_view.add_item(skip)
        con_view.add_item(loop)
        con_view.add_item(shuffle)
        con_view.add_item(playlistb)
        con_view.add_item(titel)

        await i.response.defer()

        # setup voice_client
        if i.guild.voice_client is None:
            self.voice_channel[guild] = i.user.voice.channel
            self.vc[guild]: nextcord.VoiceClient = await self.voice_channel[guild].connect()

        # reload voice_channel

        # differentiate normal search from urls
        urls = []
        data = None
        playlist = False
        is_spotify = False
        playlist_name = ""
        wait_result = False
        list_count = 0
        query = True
        if validators.url(search):
            if search.startswith(tuple(self.spotify_urls)):
                is_spotify = True
                query = False
                hasplaylist = search.count("/playlist/")
                if hasplaylist:
                    playlist = True
                    # Playlist-Daten abrufen und speichern
                    playlist_data = self.get_playlist_tracks(search)
                    if self.song_count[guild] == 0:
                        videosSearch = VideosSearch(f"{playlist_data[0]['title']} {playlist_data[0]['artist']}",
                                                    limit=1)
                        videosResult = await videosSearch.next()

                        data = self.ydl.extract_info(videosResult['result'][0]['link'],
                                                     download=False)
                        url = data['url']
                        self.playing[guild] = data
                        self.vc[guild].play(nextcord.FFmpegPCMAudio(url,
                                                                    **self.FFMPEG_OPTIONS),
                                            after=lambda e: asyncio.run(self.track_end(guild)))
                        self.vc[guild].source = nextcord.PCMVolumeTransformer(self.vc[guild].source,
                                                                              volume=0.75)
                        self.playing[guild]['started'] = datetime.datetime.now()
                        self.custom_volume[guild] = 100
                        await asyncio.sleep(1)
                        self.song_count[guild] += 1
                        list_count += 1

                        urls.append(url)
                        playlist_data.pop(0)
                    for track in playlist_data:
                        videosSearch = VideosSearch(f"{track['title']} {track['artist']}",
                                                    limit=1)
                        videosResult = await videosSearch.next()
                        data = self.ydl.extract_info(videosResult['result'][0]['link'],
                                                     download=False)
                        url = data['original_url']
                        urls.append(url)
                        playlist_data.remove(track)

                else:
                    query = True
                    track_id = self.get_spotify_track_id(search)
                    track = self.sp.track(track_id)
                    search = f"{track['name']} {track['artists'][0]['name']}"
            elif search.startswith(tuple(self.yt_urls)):
                query = False
                is_music = search.count("/music.")
                if is_music:
                    search = search.replace("/music.",
                                            "/")
                hasplaylist = search.count("/playlist")
                if hasplaylist:
                    playlist = True
                    myplaylist = Playlist(search)
                    playlist_name = myplaylist.title
                    for url in myplaylist:
                        urls.append(url)
                    self.playlists[guild] = {
                        playlist_name: urls}
                else:
                    data = self.ydl.extract_info(search,
                                                 download=False)
                    url = data['url']
                    self.song_count[guild] += 1
                    if self.song_count[guild] == 1:
                        self.playing[guild] = data
                        await i.send(f"Spielt jetzt:\n`{data['title']}`\nvon\n`{data['channel']}`\nDieses Kontrollfeld mit `/controller` öffnen",
                                     view=con_view)
                        self.vc[guild].play(nextcord.FFmpegPCMAudio(url,
                                                                    **self.FFMPEG_OPTIONS),
                                            after=lambda e: asyncio.run(self.track_end(guild)))
                        self.vc[guild].source = nextcord.PCMVolumeTransformer(self.vc[guild].source,
                                                                              volume=0.75)
                        self.playing[guild]['started'] = datetime.datetime.now()
                        self.custom_volume[guild] = 100
                    else:
                        self.queue[guild].append(data)
                        if self.shuffle[guild]:
                            self.unshuffled_queue[guild].append(data)
                        await i.send(f"`{data['title']}` von `{data['channel']}` "
                                     f"zur Warteschlange hinzugefügt.",
                                     delete_after=5,
                                     ephemeral=True)
            else:
                return await i.send(content="Ungültiger Link! Bitte überprüfe deine Eingabe\nFür mehr Infos `/music`",
                                    ephemeral=True,
                                    delete_after=15)

        if query:
            playlist = False
            # try:
            # search on yt
            videosSearch = VideosSearch(search,
                                        limit=10)
            videosResult = await videosSearch.next()

            results = []
            result_count = 0

            for entry in videosResult['result']:
                result_count += 1
                if result_count == 10:
                    break
            if result_count == 0:
                result_count = 1
            options = []
            for x in range(result_count):
                results.append(videosResult['result'][x])

                options.append(nextcord.SelectOption(label=results[x]['title'],
                                                     description=f"Von: {results[x]['channel']['name']}",
                                                     value=str(x)))

            view_results = View(timeout=15)
            show_results = Select(options=options,
                                  placeholder=f"{str(result_count)} Suchergebnisse")

            async def show_results_callback(interaction):
                x = int(show_results.values[0])
                data = self.ydl.extract_info(results[x]['link'],
                                             download=False)
                url = data['url']

                # play
                self.song_count[guild] += 1
                if self.song_count[guild] == 1:
                    self.playing[guild] = data
                    await i.send(f"Spielt jetzt:\n`{data['title']}`\nvon\n`{data['channel']}`\nDieses Kontrollfeld mit `/controller` öffnen",
                                 view=con_view)
                    self.vc[guild].play(nextcord.FFmpegPCMAudio(url,
                                                                **self.FFMPEG_OPTIONS),
                                        after=lambda e: asyncio.run(self.track_end(guild)))
                    self.vc[guild].source = nextcord.PCMVolumeTransformer(self.vc[guild].source,
                                                                          volume=0.75)
                    self.playing[guild]['started'] = datetime.datetime.now()
                    self.custom_volume[guild] = 100
                else:
                    self.queue[guild].append(data)
                    if self.shuffle[guild]:
                        self.unshuffled_queue[guild].append(data)
                    await i.send(f"`{data['title']}` von `{data['channel']}` "
                                 f"zur Warteschlange hinzugefügt.",
                                 delete_after=5,
                                 ephemeral=True)

            show_results.callback = show_results_callback
            view_results.add_item(show_results)
            await i.send(content=f"Suche: `{str(search)}`\n",
                         view=view_results,
                         delete_after=15,
                         ephemeral=True)

        # add playlist to queue
        if playlist:
            for url in urls:
                if self.song_count[guild] <= 30:
                    if self.song_count[guild] == 0 and not is_spotify:
                        data = self.ydl.extract_info(url,
                                                     download=False)
                        url = data['url']
                        self.playing[guild] = data
                        self.vc[guild].play(nextcord.FFmpegPCMAudio(url,
                                                                    **self.FFMPEG_OPTIONS),
                                            after=lambda e: asyncio.run(self.track_end(guild)))
                        self.vc[guild].source = nextcord.PCMVolumeTransformer(self.vc[guild].source,
                                                                              volume=0.75)
                        self.playing[guild]['started'] = datetime.datetime.now()
                        self.custom_volume[guild] = 100
                        await asyncio.sleep(1)
                        self.song_count[guild] += 1
                        list_count += 1

                    else:
                        try:
                            data = self.ydl.extract_info(url,
                                                         download=False)
                            self.queue[guild].append(data)
                            if self.shuffle[guild]:
                                self.unshuffled_queue[guild].append(data)
                            self.song_count[guild] += 1
                            list_count += 1
                        except Exception as e:
                            print("playlist_load fehler:")
                            print(e)
                            await i.send(f"Ein Titel war nicht verfügbar und wurde übersprungen!",
                                         ephemeral=True,
                                         delete_after=5)
                else:
                    break
            await i.send(content=f"Die ersten {str(list_count)} Titel von `{playlist_name}` wurden zur Warteschlange hinzugefügt!")
            await i.send(f"Dieses Kontrollfeld mit `/controller` öffnen",
                         view=con_view)
            return

    @nextcord.slash_command(name="music",
                            description="Informationen zum Musikbot")
    async def music(self, i: Interaction):
        await i.send(f"""```

    - Kontrolle -

    /play <Titel/URL>                  - YT-Song/Playlist abspielen
    /controller                        - Öffnet ein Kontroll Panel

    /stop                              - Ragequit >_<
    /pause                             - Wiedergabe pausieren
    /weiter                            - Wiedergabe fortsetzen
    /skip                              - Aktuelles Lied überspringen
    /playlist                          - Die aktuelle Playlist
    /loop                              - Wiederholung: Ein Toggle mit 3 Stufen
            -> 0: aus, 1: aktueller Titel, 2: aktuelle Playlist

    /join                              - Ich komme zu dir :3
    /shuffle                           - Playlist zufällig wiedergeben

    - Suchoptionen -

    - Suchfunktion                    - Mit Stichwörtern auf YT-Music suchen


    Akzeptierte URL Formate:
{self.yt_urls}

```
""",
                     ephemeral=True)

    @nextcord.slash_command(name="join",
                            description="Ich komm zu dir c:")
    async def join(self, i: Interaction):
        guild = i.guild.id
        await asyncio.create_task(self.check_guild(guild))
        if not i.user.voice:
            return await i.send("Du musst in einem Channel sein!",
                                ephemeral=True,
                                delete_after=5)
        # setup voice_client
        if self.vc[guild] is None:
            self.voice_channel[guild] = i.user.voice.channel
            self.vc[guild]: nextcord.VoiceClient = await self.voice_channel[guild].connect()
            self.vc[guild].source = nextcord.PCMVolumeTransformer(self.vc[guild].source,
                                                                  volume=0.75)
            await i.send("Halli hallo, da bin ich ^^",
                         ephemeral=True,
                         delete_after=5)
        # reload voice_channel
        elif self.vc[guild] != None:
            if self.voice_channel[guild] != i.user.voice.channel:
                await self.vc[guild].move_to(i.user.voice.channel)
                await i.send("Da bin ich auch schon :D",
                             ephemeral=True,
                             delete_after=5)
            else:
                return await i.send("Ich bin doch schon da ^^",
                                    ephemeral=True,
                                    delete_after=5)
        else:
            return await i.send("Hmm, da ist was schief gelaufen. Melde dich bei einem Admin :/",
                                ephemeral=True,
                                delete_after=5)

    @nextcord.slash_command(name="loop",
                            description="Bis zur Unendlichkeit... UND NOCH VIEL WEITER!")
    async def loop_function(self, i: Interaction):
        guild = i.guild.id
        await asyncio.create_task(self.check_guild(guild))
        if not i.user.voice:
            return await i.send("Du musst in einem Voice-Channel sein!",
                                ephemeral=True,
                                delete_after=5)
        if not i.guild.voice_client:
            return await i.send("Der Bot ist noch nicht verbunden!",
                                ephemeral=True,
                                delete_after=5)
        if not self.vc[guild].is_playing():
            return await i.send("Vorher musst du ein Lied abspielen ;)",
                                ephemeral=True,
                                delete_after=5)
        if self.loop[guild] == 0:
            self.loop[guild] = 1
            return await i.send("Der aktuelle Track wird wiederholt! :)",
                                ephemeral=True,
                                delete_after=5)
        if self.loop[guild] == 1:
            if self.song_count[guild] >= 2:
                self.loop[guild] = 2
                return await i.send("Die aktuelle Playlist wird wiederholt! :)",
                                    ephemeral=True,
                                    delete_after=5)
            else:
                pass
        self.loop[guild] = 0
        return await i.send("Wiederholung deaktiviert! :)",
                            ephemeral=True,
                            delete_after=5)

    @nextcord.slash_command(name="playlist",
                            description="Willst du wissen, was als nächstes gespielt wird?")
    async def playlist(self, i: Interaction):
        guild = i.guild.id
        await asyncio.create_task(self.check_guild(guild))
        if self.vc[guild] is None:
            return await i.send("Es läuft garnischt :D",
                                ephemeral=True,
                                delete_after=5)

        if self.song_count[guild] <= 1:
            return await i.send("Die Warteschlange ist leer, füg doch was hinzu ;D",
                                ephemeral=True,
                                delete_after=5)

        queueVar = ""
        count = 1
        if self.shuffle[guild]:
            queueVar += "**Shuffle ist aktiviert**\n\n"
        if self.loop[guild] == 1:
            queueVar += f"**Aktueller Track wird wiederholt!**\n{self.playing[guild]['title']} von {self.playing[guild]['channel']}\n\n"
        if self.loop[guild] == 2:
            queueVar += "**Aktuelle Warteschlange wird wiederholt!**\n\n"
        # todo
        #  add self.playlists position count and make it compatible with self.queue
        #
        for song in self.queue[guild]:
            if song['title'] in self.playlists:
                queueVar += f"Playlist: "
            queueVar += f"**{count}:**\n`{song['title']}`\n"
            count += 1
        em = nextcord.Embed(title="Warteschlange",
                            description=queueVar)
        await i.send(embed=em,
                     ephemeral=True,
                     delete_after=45)

    @nextcord.slash_command(name="pause",
                            description="Wiedergabe pausieren.")
    async def pause(self, i: Interaction):
        guild = i.guild.id
        await asyncio.create_task(self.check_guild(guild))
        if not i.guild.voice_client:
            return await i.send("Du kannst nichts pausieren, was nicht läuft ツ",
                                ephemeral=True,
                                delete_after=5)
        elif not i.user.voice:
            return await i.send("Du musst in einem Channel sein!",
                                ephemeral=True,
                                delete_after=5)
        elif self.voice_channel[guild].id != i.user.voice.channel.id:
            return await i.send("Wir müssen im gleichen Voice-Channel sein!",
                                ephemeral=True,
                                delete_after=5)

        self.vc[guild].pause()
        await i.send("Wiedergabe pausiert!",
                     ephemeral=True,
                     delete_after=5)

    @nextcord.slash_command(name="weiter",
                            description="Wiedergabe fortsetzen.")
    async def resume(self, i: Interaction):
        guild = i.guild.id
        await asyncio.create_task(self.check_guild(guild))
        if not i.guild.voice_client:
            return await i.send("Es lief nie Musik... ¯\_(ツ)_/¯",
                                ephemeral=True,
                                delete_after=5)
        elif not i.user.voice:
            return await i.send("Du musst in einem Channel sein!",
                                ephemeral=True,
                                delete_after=5)
        elif self.voice_channel[guild].id != i.user.voice.channel.id:
            return await i.send("Wir müssen im gleichen Voice-Channel sein!",
                                ephemeral=True,
                                delete_after=5)

        self.vc[guild].resume()
        await i.send("Wiedergabe fortgesetzt!",
                     ephemeral=True,
                     delete_after=5)

    @nextcord.slash_command(name="stop",
                            description="Bot kicken! :O")
    async def stop(self, i: Interaction):
        guild = i.guild.id
        await asyncio.create_task(self.check_guild(guild))
        if self.vc[guild] is None:
            return await i.send("Ich bin doch gar nicht da?",
                                ephemeral=True,
                                delete_after=5)
        # ToDo
        #  dj = i.guild.get_role(1109137320222924975)
        #  if dj in i.user.roles:
        #     pass
        elif not i.user.voice:
            return await i.send("Du musst in einem Channel sein!",
                                ephemeral=True,
                                delete_after=5)
        elif self.voice_channel[guild].id != i.user.voice.channel.id:
            return await i.send("Wir müssen im gleichen Voice-Channel sein!",
                                ephemeral=True,
                                delete_after=5)

        # Reset everything
        await self.vc[guild].disconnect(force=True)
        self.vc[guild].cleanup()
        self.vc[guild] = None
        self.voice_channel[guild] = None
        self.loop[guild] = 0
        self.shuffle[guild] = False
        self.shuffled[guild] = 0
        self.position[guild] = 0
        self.queue[guild] = []
        self.playing[guild] = None
        self.song_count[guild] = 0
        self.skipped[guild] = False
        await i.send("Nagut, ich geh ja schon ಥ_ಥ",
                     ephemeral=True,
                     delete_after=5)

    @nextcord.slash_command(name="shuffle",
                            description="Zufällige Wiedergabe der Warteschlange")
    async def shuffle_function(self, i: Interaction):
        guild = i.guild.id
        await asyncio.create_task(self.check_guild(guild))
        if self.vc[guild] is None:
            return await i.send("Bot nicht verbunden",
                                ephemeral=True,
                                delete_after=5)
        if not i.user.voice:
            return await i.send("Wir müssen im gleichen Voice-Channel sein!",
                                ephemeral=True,
                                delete_after=5)
        elif self.voice_channel[guild].id != i.user.voice.channel.id:
            return await i.send("Wir müssen im gleichen Voice-Channel sein!",
                                ephemeral=True,
                                delete_after=5)
        if self.song_count[guild] <= 1:
            return await i.send("Die Warteschlange ist leer",
                                ephemeral=True,
                                delete_after=5)

        if self.shuffle[guild]:
            self.queue[guild] = self.unshuffled_queue[guild]
            self.unshuffled_queue.pop(guild)
            self.shuffle[guild] = False
            await i.send("Zufällige Wiedergabe deaktiviert!",
                         ephemeral=True,
                         delete_after=5)
        else:
            self.shuffle[guild] = True
            self.unshuffled_queue[guild] = self.queue[guild]
            self.queue[guild] = random.shuffle(self.queue[guild])
            await i.send("Zufällige Wiedergabe aktiviert!",
                         ephemeral=True,
                         delete_after=5)

    @nextcord.slash_command(name="titel",
                            description="Zeigt dir den aktuellen Titel an")
    async def titel(self, i: Interaction):
        guild = i.guild.id
        await asyncio.create_task(self.check_guild(guild))
        if not self.song_count[guild] == 0:
            await i.send(f"Aktuell spielt: `{self.playing[guild]['title']}` von `{self.playing[guild]['channel']}`\n{self.playing[guild]['original_url']}",
                         ephemeral=True,
                         delete_after=10)
        else:
            await i.send("Mach zuerst Musik an\n>>> `/play [Titel/URL]`",
                         ephemeral=True,
                         delete_after=5)

    @nextcord.slash_command(name="skip",
                            description="Aktuellen Track überspringen")
    async def skip(self, i: Interaction):
        guild = i.guild.id
        await asyncio.create_task(self.check_guild(guild))
        if self.vc[guild] is None:
            return await i.send("Bot nicht verbunden",
                                ephemeral=True,
                                delete_after=5)
        if not self.vc[guild].is_playing() and not self.vc[guild].is_paused():
            return await i.send("Ich spiel doch garnichts?",
                                ephemeral=True,
                                delete_after=5)
        if not i.user.voice:
            return await i.send("Du musst in einem Voice-Channel sein!",
                                ephemeral=True,
                                delete_after=5)
        elif self.voice_channel[guild].id != i.user.voice.channel.id:
            return await i.send("Wir müssen im gleichen Voice-Channel sein!",
                                ephemeral=True,
                                delete_after=5)
        if self.song_count[guild] <= 1:
            return await i.send("Die Warteschlange ist leer",
                                ephemeral=True,
                                delete_after=5)

        self.vc[guild].stop()
        self.skipped[guild] = True
        await i.send(f"`{self.playing[guild]['title']}` übersprungen!",
                     ephemeral=True,
                     delete_after=5)
        # self.vc[guild].stop() triggers track_end() ergo it deletes current song


async def setup(bot):
    bot.add_cog(music(bot))
