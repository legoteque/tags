timings = False
load_export_path = False

import time
import os, re, random, math, vlc, json, mutagen
import pandas as pd
import tkinter as tk
import tkinter.simpledialog
from tkinter import ttk, filedialog, messagebox
from legoteca import ItunesLibrary, AudioFile, Spotify
from legoteca import ms_to_string, remote_xml_conected_assert
from utilities import Linker
from utilities import extract_pic_from_metadata, bpms_iguals_o_multiples, key_from_value
from utilities import format_spaces

import warnings
warnings.filterwarnings("ignore", 'This pattern has match groups')

#CONSTANTS

with open('data.json') as json_file:
    data = json.load(json_file)  
EXPORT_PATH = data["DATA"]["EXPORT_PATH"]

PATTERN = {"genre": r"^\!\d\d \![\w\&]+\b",
           "subgenre": r"\B![A-Z][\w\&]+\b",
           "desc_subgenre": r"\B\.\w{2,5}\b",
           "rating": r"\B\*\B|\B\'z{1,4}p?\'\B",
           "club": r"\B\@\S{3,5}\b",
           "generation": r"\B\:[C,B,X,Y,Z]\b",
           "year": r"^\d{4}$",
           "bpm": r"^(([4-9][0-9])|1[0-9][0-9]|2[0-9][0-9])$"}

#valors i noms de les variables de checkbox (no és una descripció, serveix per definirles)
TYPE_SUBGENRE = {"rebeat": ".rb", "doubletempo": ".dt", "halftempo": ".ht", "dembowed": ".dmbw", 
                 "cover": ".co", "remix": ".rmx", "mashup": ".mu",
                 "alternative": ".AH",  "mainstream": ".MS"}

DESC_SUBGENRE = {".mel": "Melodic", ".hpy": "Happy", ".drk": "Dark",
                 ".chil": "Chill", ".sax": "Saxo",
                 ".epc": "Epic", ".hyp": "Hypnotic", ".atm": "Atmospheric", ".etn": "Etnic",
                 ".teen": "Teenager", ".auTu": "Autotune",
                 ".orch": "Orchestra", ".ins": "Instrumental", ".voc": "Vocal"}

HEART, STAR = "\U0001F9E1", "\U00002B50"
RATING = {"*": "*", STAR:"'z'", STAR*2: "'zz'", STAR*3: "'zzz'", STAR*4: "'zzzz'"}
RATING_IT = {"": "", "20": STAR, "40": STAR*2, "60": STAR*3, "80": STAR*4, "100": STAR*5}

GENERATION = {":Z": "Z Gen", ":Y": "Y Gen", ":X": "X Gen", ":B": "Boomer", ":C": "Classic"}



def yesno_to_bool(answer):
        if answer == "yes": return True
        if answer == "no": return False
        
        
if timings: time0 = time.time()




class Interface(tk.Tk):
    def __init__(self, it=None):
        super().__init__()
        self.title("Playlists Tagger")
        #self.geometry("1200x1000")
        self.attributes('-fullscreen', True)
        
        #afegim label loading
        self.loading_lbl = tk.Label(self, text="Reading local export path and loading playlists...", 
                                    bg="white", fg="red", font=("Courier", 30), relief="solid", borderwidth=5)
        self.loading_lbl.place(relx=.5, rely=.5, anchor=tk.CENTER)

        #mostrem el construït
        self.update()
        
        #importem els ultims unics desats
        self.load_last_saved_data()
        
        # make the top right close button minimize: self.iconify)
        #self.protocol("WM_DELETE_WINDOW", self.iconify)
        #previene la interaccion con la ventana
        #self.attributes('-disabled', True)
        # make Esc exit the program
        #self.bind('<Escape>', lambda e: self.close_app())
        
        
        #afegim shortcuts
        self.bind('<Control-d>', lambda e: self.mybpm_mult("double"))
        self.bind('<Control-h>', lambda e: self.mybpm_mult("half"))
        self.bind('<Control-r>', lambda e: self.mybpm_mult("rebeat"))

        # create a menu bar with Minimize an Exit command
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        
        menubar.add_command(label="Exit", command=self.close_app)
        menubar.add_command(label="Minimize", command=self.minimize_win)
        
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Add a path to local lists", command=self.add_local_list_to_browser)
        filemenu.add_separator()
        filemenu.add_command(label="Create audio playlist to import in Itunes", command=self.create_playlist_to_export)
        
        listmenu = tk.Menu(menubar, tearoff=0)
        listmenu.add_command(label="Prova pop-up")
        
        menubar.add_cascade(label="Utilities", menu=filemenu)
        menubar.add_cascade(label="List", menu=listmenu)
        
        #patch per poder posar colors als treeviews
        s = ttk.Style()
        def fixed_map(option):
            return [elm for elm in s.map('Treeview', query_opt=option) if elm[:2] != ('!disabled', '!selected')]
        s.map('Treeview', foreground=fixed_map('foreground'), background=fixed_map('background'))
        
        #construim layout
        self.build_media_frame()
        
        self.title_song = tk.StringVar(value="")
        self.title_song_lbl = tk.Label(self, textvariable=self.title_song, font=("Courier", 15), 
                                  padx=2, pady=2, fg="blue")
        self.title_song_lbl.pack()
        
        lower_frame = tk.Frame(self)
        lower_frame.columnconfigure(1, weight=1)
        lower_frame.pack(fill=tk.BOTH, padx=10)
        
        label = tk.Label(lower_frame, text="", bg="#444")
        label.grid(row=0, column=1, rowspan=2, sticky="NSEW")            
        
        #construim frame de tags
        tags_frame = tk.Frame(lower_frame, relief=tk.SOLID, borderwidth=1)
        tags_frame.grid(column=0, row=0, ipadx=10, ipady=10, sticky="NSEW")
        self.itunes_tags = TagsReader(self, tags_frame, frame="Itunes")
        
        #carreguem primer l'editor, doncs el reader necessita trobarlo per poder dirigirli el load
        self.editor = TagsEditor(self, lower_frame)
        # location_width defineix el tamany del frame tagsReader i ho resta de TagsEditor
        self.reader = TagsReader(self, tags_frame, frame="Metadata", location_width=85)
        
        self.build_spotify_frame()
        
        #carreguem folders
        self.build_tree_browser_from_playlists()
        
        #inicialitzem i instanciem variables de reproduccio
        self.ct = CurrentTrack(self, loaded=False)
        self.lm = ListManager(self)
        self.enable_trace_vars = True #habilitem binds (de moment a list_selected)
        self.media = None

#SHORTCUTS
    def mybpm_mult(self, multiple):
        if self.editor.editor_status.get() == "EDITOR": return
        mybpm = self.editor.tracknumber.get()        
        if multiple == "double":
            double = str(int(mybpm) * 2)
            self.editor.tracknumber.set(double)
        elif multiple == "half":
            half = str(math.ceil(int(mybpm) / 2)) #math.ceil arrodoneix a int cap a dalt
            self.editor.tracknumber.set(half)
        elif multiple == "rebeat":
            rebeat = str(math.ceil(int(mybpm) * 1.3125))
            self.editor.tracknumber.set(rebeat)

#----------------------ITUNES LIBRARY IMPORT & LISTS OF UNIQUES----------------------------
    #funció a la que passant un unique ens retorna els uniques sota un pattern
    def uniques(self, column, pattern, genre=None):
        if genre == None:
            data = self.tracks_df[column].unique()
        else:
            data = self.tracks_df[self.tracks_df.Genre == genre]
            data = data[column].unique()
        matches = []
        for value in data:
            found = re.findall(pattern, value)
            matches = matches + found
            matches = set(matches)
            matches = list(matches)
            matches.sort()
        return matches
    
    def build_uniques(self):
        #gèneres únics (son afegibles per l'usuari temporalment)
        genres_l = self.uniques("Genre", PATTERN["genre"])
        
        #subgèneres únics (son afegibles per l'usuari temporalment)
        self.subgenres_l = self.uniques("Album", PATTERN["subgenre"])
        
        #subgèneres per gènere
        self.sub_x_genre_dic = {genre: self.uniques("Album", PATTERN["subgenre"], genre) for genre in genres_l}
        
        #subgèneres descriptius únics (definits)
        self.desc_subgen_dic = DESC_SUBGENRE.copy()
        #subgéneres descriptius unics no definits(els busca a la biblioteca)
        desc_subgen_l = self.uniques("Album", PATTERN["desc_subgenre"])
        #muntem diccionari de subgèneres únics agafant la descripció de desc_subgen_dic, si la troba. Sinó igual.
        desc_subgens, desc_subtypes = list(DESC_SUBGENRE.keys()), list(TYPE_SUBGENRE.values())
        new_desc_subgen_l = [desc for desc in desc_subgen_l if desc not in desc_subgens + desc_subtypes]
        for desc in new_desc_subgen_l: self.desc_subgen_dic[desc] = desc
        
        #clubs únics
        self.clubs_l = self.uniques("Composer", PATTERN["club"])
        
        #creem un diccionari amb els unics cada cop que llegim per la propera vegada que obrim poder omplir els comboxes
        uniques_dic = {"subgenres_l": self.subgenres_l,
                       "sub_x_genre_dic": self.sub_x_genre_dic,
                       "desc_subgen_dic": self.desc_subgen_dic,
                       "clubs_l": self.clubs_l}
        
        with open('temp/uniques.json', 'w') as f:
            json.dump(uniques_dic, f)

    def load_last_saved_data(self):
        with open('temp/uniques.json') as f:
            uniques_dic = json.load(f)
            
        self.subgenres_l = uniques_dic["subgenres_l"]
        self.sub_x_genre_dic = uniques_dic["sub_x_genre_dic"]
        self.desc_subgen_dic = uniques_dic["desc_subgen_dic"]
        self.clubs_l = uniques_dic["clubs_l"]
        
        #importem l'última versio carregada de playlists_df
        self.playlists_df = pd.read_csv("temp/playlists_df.csv", keep_default_na=False)
        #importem l'ultima versió llegida de tracks_df
        self.tracks_df = pd.read_csv("temp/tracks_df.csv", dtype={"BPM": "str"}, keep_default_na=False)
        #importem l'ultima versió llegida de finder_df
        finder_df = pd.read_csv("temp/finder_df.csv")
        finder_df.fillna("", inplace=True)
        self.linker = Linker(self.tracks_df, finder_df=finder_df)
    
    def import_itunes_library_and_linker(self):
        it = ItunesLibrary(xml_local_path=None, max_tracks_pl=2000)
        #If there are duplicated tracks
        if it.hay_duplicated_locs | it.hay_duplicated_tracks:
            self.loading_lbl.destroy()
            duplicated = pd.DataFrame()
            if it.hay_duplicated_locs: duplicated = it.duplicated_locs.copy()
            if it.hay_duplicated_tracks: duplicated = pd.concat((duplicated, it.duplicated_tracks))

            duplicated.to_csv("duplicated.csv")

            msg = "\n\nCreat 'duplicated.csv' per consultar els duplicats"
            msg += "\n\n Soluciona aquests duplicats i recarrega la biblioteca"
            msg = it.import_msg + msg
            messagebox.showwarning(title="Info", message=msg)
            return        
        
        self.tracks_df = it.tracks_df
        self.linker = Linker(self.tracks_df)
        
        #apliquem filtrat de playlists d'itunes
        pattern = r"^([1-9](A|B))|(1[0-2](A|B))"
        cond1 = it.playlists_df.List.str.contains(pattern)
        cond2 = it.playlists_df.Folder.str.contains("^--")
        it_playlists_df = it.playlists_df[~cond1 & ~cond2].copy()
        
        local_playlists_df = self.playlists_df[self.playlists_df.Folder == "LOCAL"]
        self.playlists_df = pd.concat([local_playlists_df, it_playlists_df])
        self.playlists_df.reset_index(drop=True, inplace=True)
        self.playlists_df.fillna("", inplace=True)
        
        return it.msg
    
        
#BUILD MEDIA
    def build_media_frame(self):   
        media_frame = tk.Frame(self, relief=tk.SOLID, borderwidth=2)
        media_frame.columnconfigure(1, weight=1)
        media_frame.pack(fill=tk.BOTH, padx=10)
        
        navigator_frame = tk.Frame(media_frame, relief='raised', borderwidth=1, bg="#333")
#         -----------
        itunes_bar = tk.Frame(navigator_frame, bg="black")
        
        import_library_btn = tk.Button(itunes_bar, text="Import Library", command=self.import_itunes_to_browser)
        search_library_btn = tk.Button(itunes_bar, text="Search in Library")
        
        import_library_btn.grid(row=0, column=0, padx=2)
        search_library_btn.grid(row=0, column=1, padx=2)
#         -----------
        lists_bar = tk.Frame(navigator_frame, bg="black")
    
        add_local_list_btn = tk.Button(lists_bar, text="Add Local", command=self.add_local_list_to_browser)
        self.remove_list_btn = tk.Button(lists_bar, text="Remove", command=self.remove_list_from_browser)
        self.refresh_list_btn = tk.Button(lists_bar, text="Refresh", command=self.refresh_list_from_browser)
        
        add_local_list_btn.grid(row=0, column=0, padx=2)
#         -----------
        navigator_bar = tk.Frame(navigator_frame, bg="black")
                
        self.sortby_cb = tk.StringVar(value="Creation (desc.)")
        self.sort_cb = ttk.Combobox(navigator_bar, textvariable=self.sortby_cb, height=30, width=11,
                               values=["Artist", "Position", "Creation (asc.)", "Creation (desc.)", "Modified (asc.)", "Modified (desc.)"])
        self.sort_cb.bind('<<ComboboxSelected>>', self.list_selected)
        
        
        self.origin_route = tk.StringVar(value="Local mode")
        self.origin_route_cb = ttk.Combobox(navigator_bar, textvariable=self.origin_route, 
                               values=["Find remotes", "Local mode"], height=30, width=12)
                               
        
        self.list_btn1 = tk.Button(navigator_bar, text="Export playlist", command=self.create_playlist_to_export)
        
        self.list_btn2 = tk.Button(navigator_bar, text="Add hashtag", command=self.add_hashtag_to_list)
                                               
        self.list_btn3 = tk.Button(navigator_bar, text="Build new tracks folder", command=self.build_new_tracks_folder)                                       
                                               
#         -----------
        self.folder_list = ttk.Treeview(navigator_frame, height=13, selectmode="browse")
        self.folder_list.tag_bind("selected", "<<TreeviewSelect>>", self.folder_selected)
        self.folder_list.heading("#0", text="Folders")
        
        self.list_list = ttk.Treeview(navigator_frame, height=13, selectmode="browse")
        self.list_list.tag_bind("selected", "<<TreeviewSelect>>", self.list_selected)
        
        self.list_list.heading("#0", text="Lists")
        
        self.audio_list = ttk.Treeview(navigator_frame, height=13, columns=("artist", "title", "level"), selectmode="browse")
        self.audio_list.tag_bind("selected", "<<TreeviewSelect>>", self.audio_selected)
        self.audio_list_sb = ttk.Scrollbar(navigator_frame, orient="vertical", command=self.audio_list.yview)
        self.audio_list.configure(yscrollcommand=self.audio_list_sb.set)
        self.audio_list.heading("#0", text="Nº")
        self.audio_list.column("#0", minwidth=0, width=41, stretch=tk.NO)
        self.audio_list.heading("artist", text="Artist")
        self.audio_list.column("artist", minwidth=0, width=250, stretch=tk.NO)
        self.audio_list.heading("title", text="Title")
        self.audio_list.column("title", minwidth=0, width=449, stretch=tk.NO)
        self.audio_list.heading("level", text="L")
        self.audio_list.column("level", minwidth=0, width=25, stretch=tk.NO)
        
        
        itunes_bar.grid(row=0, column=0, sticky="NSEW")
        lists_bar.grid(row=0, column=1, sticky="NSEW")
        navigator_bar.grid(row=0, column=2, sticky="NSEW")

        self.folder_list.grid(row=1, column=0)
        self.list_list.grid(row=1, column=1)
        self.audio_list.grid(row=1, column=2)
        self.audio_list_sb.grid(row=1, column=3, sticky="nse")
#---------------------------------------------
        self.route_song = tk.StringVar(value="")
        route_song_lbl = tk.Label(media_frame, textvariable=self.route_song, font=("Courier", 11), 
                                  fg="white", bg="#666", height=3, borderwidth=4, relief=tk.SOLID)
   
        self.player_frame = tk.Frame(media_frame, relief='raised', borderwidth=30, bg="#044")
    
        back_btn = tk.Button(self.player_frame, text="back", relief="raised", borderwidth=5,
                                  command = lambda: self.change_song(-1))
        jump15back = tk.Button(self.player_frame, text="-15", relief="raised", borderwidth=5, 
                                    command = lambda: self.jump(-15))
        play_btn = tk.Button(self.player_frame, text="play", relief="raised", borderwidth=5, command=self.play)
        pause_btn = tk.Button(self.player_frame, text="pause", relief="raised", borderwidth=5, command=self.pause)
        stop_btn = tk.Button(self.player_frame, text="stop", relief="raised", borderwidth=5, command=self.stop)
        jump15frwd = tk.Button(self.player_frame, text="+15", relief="raised", borderwidth=5, 
                                    command = lambda: self.jump(15))
        next_btn = tk.Button(self.player_frame, text="next", relief="raised", borderwidth=5,
                                  command = lambda: self.change_song(1))
        
        self.time_song = tk.StringVar(value="")
        self.time_song_lbl = tk.Label(self.player_frame, textvariable=self.time_song, font=("Courier", 20),
                                      bg="#044", fg="white", padx=2, pady=10, foreground="yellow")
        self.perc_song = tk.StringVar(value="")
        self.perc_song_lbl = tk.Label(self.player_frame, textvariable=self.perc_song, font=("Courier", 20),
                                      bg="#044", fg="white", padx=2, pady=10, foreground="yellow")
        self.song_dur = tk.StringVar(value="")
        self.song_dur_lbl = tk.Label(self.player_frame, textvariable=self.song_dur, font=("Courier", 15),
                                      bg="#044", fg="white", padx=2, pady=10, foreground="yellow")
        
        self.random = tk.BooleanVar(self)
        random_cb = ttk.Checkbutton(self.player_frame, text="Shuffle ", variable=self.random)
        
        self.volume_sc = tk.Scale(self.player_frame, from_=1, to=100, orient=tk.HORIZONTAL, showvalue=0, resolution=1, 
                       command=self.set_volume)
        self.volume_sc.set(100)

        back_btn.grid(row=0, column=0)
        jump15back.grid(row=0, column=1)
        play_btn.grid(row=0, column=2)
        pause_btn.grid(row=0, column=3)
        stop_btn.grid(row=0, column=4)
        jump15frwd.grid(row=0, column=5)
        next_btn.grid(row=0, column=6)
        self.time_song_lbl.grid(row=1, column=0, columnspan=3)
        self.perc_song_lbl.grid(row=1, column=3, columnspan=2)
        self.song_dur_lbl.grid(row=1, column=5, columnspan=2)
        random_cb.grid(row=2, column=5, columnspan=2)
        self.volume_sc.grid(row=2, column=0, columnspan=5, sticky="EW")
#---------------------------------------------
        self.label_art = tk.Label(media_frame, bg="white", relief="solid")
        #carreguem l'art
        image = extract_pic_from_metadata(None, size=(311,311), return_logo=True)
        self.label_art.config(image=image)
        self.label_art.image=image
        
        navigator_frame.grid(row=0, column=0)
        route_song_lbl.grid(row=0, column=1, sticky="NEW")
        self.player_frame.grid(row=0, column=1)
        self.label_art.grid(row=0, column=2, sticky="NSEW")

    def build_spotify_frame(self):
        frame5 = tk.Frame(self, bg="black")
        frame5.columnconfigure(0, weight=1)
        frame5.pack(padx=10, pady=5, fill=tk.BOTH, expand=True) 

#---------------------------------------PLAYER FUNTIONS----------------------------------

    def player_instance(self, playing_path, autoadvance):
        del self.media
        #generem instancia del nou track
        self.media = MusicPlayer(playing_path)
        pevent = self.media.audio.event_manager()
        pevent.event_attach(vlc.EventType.MediaPlayerPositionChanged, self.pos_callback)
        if autoadvance:
            pevent.event_attach(vlc.EventType.MediaPlayerEndReached, lambda e: self.change_song(1))
        
    def pos_callback(self, event):
        self.time_song.set(self.media.playing_time())
        position = int(self.media.audio.get_position() * 100)
        self.perc_song.set(str(position)+"%")
        
    def play_path(self, playing_path=None, prelisten=None):
        if prelisten != None:
            if prelisten == "select": playing_path = self.ct.itunes_link_loc[1]
            elif prelisten == "button":
                if self.ct.playing_origin == "Local": playing_path = self.ct.itunes_link_loc[1]
                else: playing_path = self.ct.pc_loc
            autoadvance = False
            if self.media.audio.is_playing():
                if self.media.song_path == playing_path: return
                else: self.media.audio.stop() #si seleccionem qualsevol altre track aturem
            #check if file exists
            if not os.path.isfile(playing_path):
                msg = f"No connection to {playing_path}."
                messagebox.showinfo(title="Info", message=msg)   
                if hasattr(self.itunes_tags, 'window'): self.itunes_tags.window.destroy()   
                return          
            
            #canviem el color del player si es prelisten
            self.player_frame.config(bg="red")
            self.time_song_lbl.config(bg="red", foreground="black")
            self.perc_song_lbl.config(bg="red", foreground="black")
            self.song_dur_lbl.config(bg="red", foreground="black")
        else: 
            autoadvance = True
            #color del player
            self.player_frame.config(bg="#044")
            self.time_song_lbl.config(bg="#044", foreground="yellow")
            self.perc_song_lbl.config(bg="#044", foreground="yellow")
            self.song_dur_lbl.config(bg="#044", foreground="yellow")
        
        self.player_instance(playing_path, autoadvance)
        duration = mutagen.File(playing_path).info.length
        duration = ms_to_string(duration, metric="seconds")
        self.song_dur.set(duration)
        self.play()
        
    def play(self):
        if not self.ct.loaded: return
        self.time_song.set("Loading")
        self.perc_song.set("")
        self.media.audio.play()
        
    def stop(self):
        if not self.ct.loaded: return
        self.media.audio.stop()
        self.time_song.set("0:00")
        self.perc_song.set("0%")
        
    def pause(self):
        if not self.ct.loaded: return
        self.media.audio.pause()
            
    def jump(self, sec):
        if not self.ct.loaded: return
        if self.media.audio.is_playing(): self.media.jump(sec)
            
    def change_song(self, jump):
        if not self.ct.loaded: return
        if self.media.audio.is_playing(): self.media.audio.stop()
        folder_iid, lista_iid = self.ct.folder_iid, self.ct.list_iid
        audio_iid, list_len = self.ct.audio_iid, self.ct.Length
  
        #si som a una llista diferent (except controla la possiblitat que no hi hagi llista seleccionada) no fa res
        try:
            list_selection_iid = self.list_list.selection()[0]
        except: return
        if list_selection_iid != lista_iid: return
        #si esta ubicat en el seu folder i llista posem el focus sobre el track actual
        self.audio_list.focus(audio_iid)
        if self.random.get():
            possible_next = list(range(int(list_len)))
            possible_next.remove(int(audio_iid))
            next_audio_iid = str(random.choice(possible_next))
        else:
            next_audio_iid = str(int(audio_iid) + jump)
        #si el track cridat esta fora de rang evitem l'excepció
        try:
            self.audio_list.selection_set(next_audio_iid)
        except: return
            
    def set_volume(self, e):
        if not self.ct.loaded: return
        value = int(math.log(self.volume_sc.get(), 1.047))
        self.media.audio.audio_set_volume(value)


    def close_app(self):
        self.stop()
        self.destroy()
        
    def minimize_win(self):
        self.wm_state('iconic')

        
#-----------------------------------FUNCIONS PER EDITAR LLISTES-------------------------- 
    def save_playlists_df(self):
        #esborrem columnes iid si les hem creat amb les funcions de llista
        playlists_df = self.playlists_df.copy()
        del_columns = ["folder_iid", "list_iid", "audio_iid"]
        for col in del_columns:
            if col in playlists_df: playlists_df.drop(columns=col, inplace=True)
        
        playlists_df.to_csv("temp/playlists_df.csv", index=False)
        
    def local_last_list_selection(self, event):
        local_playlists = self.playlists_df[self.playlists_df.Folder == "LOCAL"]
        last_list_iid = len(local_playlists["List"].unique()) - 1
        
        if not last_list_iid < 0: 
            self.list_list.selection_set(last_list_iid)
            self.list_selected(event)
        
    def return_folder_list_selected(self, return_ids=False):
        list_iid = self.list_list.selection()[0]
        lista = self.list_list.item(list_iid, option="text")
        values = self.list_list.item(list_iid, option="values")
        folder_iid, folder = values[0], values[1]
        
        if return_ids: return folder, lista, folder_iid, list_iid
        return folder, lista
    
    def append_list_to_playlists(self, new_list_df):
        #ubiquem la nova llista darrera de les locals existents
        local_playlists_df = self.playlists_df[self.playlists_df.Folder == "LOCAL"].copy()
        local_playlists_df = pd.concat([local_playlists_df, new_list_df])
        #eliminem locals de playlists_df 
        index = self.playlists_df[self.playlists_df.Folder == "LOCAL"].index
        self.playlists_df.drop(index=index, inplace=True)
        #afegim playlists locals ordenades davant itunes playlists
        self.playlists_df = pd.concat([local_playlists_df, self.playlists_df])
        self.playlists_df.reset_index(drop=True, inplace=True)
        self.playlists_df.fillna("", inplace=True)
        
        self.save_playlists_df()
# ----------
#new_tracks_folder especifica a select_list la seleccio de export
    def add_local_list_to_browser(self, new_tracks_folder_path=None): 
        def extract_path(pathfile):
            pathfile = pathfile.split(os.sep)[:-1]
            return os.sep.join(pathfile)
        
        if new_tracks_folder_path == None: #add new list
            #busquem els paths locals ja agregats a les llistes
            path_s = self.playlists_df[self.playlists_df.Folder == "LOCAL"]["pc_loc"].apply(extract_path)

            path = filedialog.askdirectory(initialdir=EXPORT_PATH, title='Select path to add as a list')
            path = path.replace("/", os.sep)
            #si el path no pertany a la carpeta compartida amb mac o el path ja ha estat agregat com a llista sortim
            if (EXPORT_PATH not in path) | (path in path_s.values): 
                if EXPORT_PATH not in path: msg = "It's not possible to add a folder not shared with mac"
                if path in path_s.values: msg = "This path has already been added as a list"
                messagebox.showwarning(message=msg, title="Error")
                return
        
        #en el cas que sigui un add_new_tracks_folder
        else: path, subfolders = new_tracks_folder_path, False
        
        time0 = time.time()
        folder_playlist_df = self.linker.build_loc_path_synched_df(path, subfolders=False)
        time1= time.time()
        
        self.append_list_to_playlists(folder_playlist_df)
        
        #esborrem folders per si no estem a LOCAL, o no nhi ha, al donar-li add
        self.delete_audio_tree(lista=True, folder=True)
        self.build_tree_browser_from_playlists()
        
        #folder_iid=0 sera LOCAL i hi ha d'haver locals pq n'acabem d'agregar
        self.folder_list.selection_set(0)
        self.folder_selected(None)
        self.local_last_list_selection(event="add")
        
        lista = path.split(os.sep)[-1]
        messagebox.showinfo(title="Info", message=f"Afegit {lista} a LOCAL en {time1 - time0:.2f}s.")
            
    def delete_track(self, later=False):
        #si no hi ha cap track seleccionat retorna
        if not self.ct.loaded: return
        if self.ct.file_origin == "Itunes": return
        
        if not later: #delete forever
            msg = f"Do you want to delete {self.ct.pc_loc}?"
            response = yesno_to_bool(messagebox.askquestion(message=msg, title="Question"))
            if not response: return
        
        self.media.audio.stop()
        
        #podem agafar current en comptes de selected perquè el track s'ha de carregar obligatòriament
        list_df = self.lm.current_list_df 
        del_track_i = list_df[list_df.pc_loc == self.ct.pc_loc].index
        
        #esborrem el track a la nova llista i reubiquem positions
        new_list_df = list_df.drop(index=del_track_i)
        new_list_df["Position"] = range(len(new_list_df))
        new_list_df["Length"] = len(new_list_df)
        
        #esborrem la llista original de playlists_df i afegim la nova
        self.playlists_df.drop(index=list_df.index, inplace=True)
        self.append_list_to_playlists(new_list_df)
               
        if later: #si no es un delete movem el track a EXPORT_PATH
            filename = self.ct.pc_loc.split(os.sep)[-1]
            new_filepath = EXPORT_PATH + os.sep + filename
            os.replace(self.ct.pc_loc, new_filepath)
        else: os.remove(self.ct.pc_loc)

        audio_iid = self.ct.audio_iid
        self.ct.loaded = False
        self.list_selected("delete track")
        self.audio_list.selection_set(audio_iid)
        self.audio_selected(None)
    
    def remove_list_from_playlist(self, list_df):
        del_index = list_df.index
        self.playlists_df.drop(index=del_index, inplace=True)
        self.playlists_df.reset_index(drop=True, inplace=True)
    
    def remove_list_from_browser(self):
        remove_df = self.lm.selected_list_df
        self.remove_list_from_playlist(remove_df)
        self.save_playlists_df()

        #intentem agafar folder, si nhi ha. Sinó folder selected no fara res
        self.folder_selected(None)        
        #eliminem folder_list_selected de lm (pq la següent seleccionada sigui la carregada)
        self.lm._folder_list_selected = [None, None]
        #intentem seleccionar la última llista local (si nhi ha, sino no fara res)
        self.local_last_list_selection(event="delete list")
        
    def refresh_list_from_browser(self, new_tracks_folder=False):
        refresh_df = self.lm.selected_list_df
        refreshed_df, added, deleted = self.linker.build_synched_from_list_df(refresh_df)
        
        self.remove_list_from_playlist(refresh_df)
        self.append_list_to_playlists(refreshed_df)
        
        self.list_selected("refresh")
        
        if new_tracks_folder: return
        
        path_refresh = os.sep.join(refresh_df.pc_loc.iat[0].split(os.sep)[:-1])
        lista = path_refresh.split(os.sep)[-1]
        msg = f"{added} arxius nous vinculats.\n{deleted} arxius eliminats de la carpeta."
        msg = "Sense canvis." if added == deleted == 0 else msg
        messagebox.showinfo(title="Info", message=f"Llista {lista} actualitzada:\n" + msg)
    
    def import_itunes_to_browser(self):
        xml_mod_date = remote_xml_conected_assert()
        with open('data.json') as f:
            data = json.load(f) 
        if data["DATA"]["XML_MODIFIED"] == xml_mod_date:
            msg = f"Les versions del XML coincideixen de data\n{xml_mod_date}\n"
            messagebox.showinfo(title="Info", message= msg + "Si hi ha informació nova a Itunes, desa la nova versió de la biblioteca.")
            return

        self.stop()
        self.delete_audio_tree(lista=True, folder=True)#esborrem trees
        
        #mostrem label
        if self.loading_lbl.winfo_exists(): self.loading_lbl.destroy()
        self.loading_lbl = tk.Label(self, text="Reading remote iTunes library and loading playlists...",
                                    bg="white", fg="red", font=("Courier", 30), relief="solid", borderwidth=5)
        self.loading_lbl.place(relx=.5, rely=.5, anchor=tk.CENTER)
        self.update()
        
        #importem biblioteca i construim finder i recollim missatge d'importacio
        import_msg = self.import_itunes_library_and_linker()
                
        #desem tracks_df i itunes playlists
        self.tracks_df.to_csv("temp/tracks_df.csv", index=False)
        self.save_playlists_df()
        #desem finder_df --> ho fem a utilities, al thread de creació
        
        #desem la data de modificacio de l'XML importat
        data["DATA"]["XML_MODIFIED"] = remote_xml_conected_assert()
        with open('data.json', 'w') as f:
            json.dump(data, f)
                
        self.build_uniques()
          
        self.build_tree_browser_from_playlists()
        self.origin_route.set("Find remotes")

        if self.loading_lbl.winfo_exists(): 
            self.loading_lbl.destroy()
            messagebox.showinfo(title="Info", message=import_msg)
            self.list_btn1.grid_remove()
            self.list_btn2.grid_remove()
            self.list_btn3.grid_remove()

    def create_playlist_to_export(self):
        playlist = f"{self.lm._folder_list_selected[1]} (export).m3u8"
        playlist_path = EXPORT_PATH + os.sep + playlist
        list_df = self.lm.selected_list_df.copy()
        
        playlist_paths_l = list_df.apply(lambda x: x.mac_loc if x.linked else x.pc_mac_loc, axis=1).tolist()
        
        with open(playlist_path, "w", encoding='utf-8') as text_file:
            text_file.write("\n".join(playlist_paths_l))
        msg = f"\nAfegida a '{EXPORT_PATH}' la playlist '{playlist}'"
        messagebox.showinfo(title="Info", message=msg)
        
    def build_new_tracks_folder(self):
        msg = "Do you want to create a new folder with unlink tracks?"
        response = yesno_to_bool(messagebox.askquestion(message=msg, title="Question"))
        if not response: return
        
        list_df = self.lm.selected_list_df.copy()
        
        filepath0 = list_df.pc_loc.iloc[0]
        path = os.sep.join(filepath0.split(os.sep)[:-1])
        export_path = path + os.sep + "export"
        
        if not os.path.isdir(export_path): os.mkdir(export_path)
        
        cond = list_df.linked #els que no hem linkat son els exportables
        no_linked_df = list_df[~cond]
        paths_new = no_linked_df.pc_loc.tolist()
        
        for old_file_path in paths_new:
            filename = old_file_path.split(os.sep)[-1]
            new_file_path = export_path + os.sep + filename
            os.replace(old_file_path, new_file_path)
        
        self.refresh_list_from_browser(new_tracks_folder=True)
        
        #afegim el directori export com una llista (simulem un refresh del export)
        self.add_local_list_to_browser(new_tracks_folder_path=export_path)
        
        
#FUNCIONS PER EDITAR TRACKS
    def upgrade_track(self):
        #agafem localitzacions del track que es mostra a itunes panel   
        mac_loc, mac_pc_loc = self.ct.itunes_link_loc

        if self.ct.linked: self.change_link(False, upgrade=True)
        
        #afegim notacio de Esborrat i creem una llista per actualitzar aquests tracks
        audio = AudioFile(mac_pc_loc)
        audio.genre = "!99 !BORRAT"
        audio.save()

        playlist_path = os.sep.join(self.ct.pc_loc.split(os.sep)[0:-1]) + os.sep + "- ESBORRAR.m3u8"
        if os.path.exists(playlist_path):
            with open(playlist_path) as text_file:
                lines_l = text_file.readlines()
                files_l = [f.replace("\n", "") for f in lines_l]
        else: files_l = []

        if mac_loc not in files_l:
            files_l.append(mac_loc) 
            with open(playlist_path, "w", encoding='utf-8') as text_file:
                text_file.write("\n".join(files_l))

        self.editor.fill_editor_fields(mac_pc_loc)
            
         
    def change_link(self, linked, upgrade=False):
        self.media.audio.stop()
        
        index_track = self.playlists_df[self.playlists_df.Location == self.ct.Location].index
        self.playlists_df.loc[index_track, "linked"] = linked
        
        if linked:
            self.playlists_df.loc[index_track, "level"] = 6
            self.playlists_df.loc[index_track, "color"] = "red"
            self.playlists_df.loc[index_track, "mac_pc_loc"] = self.ct.itunes_link_loc[1]
            self.playlists_df.loc[index_track, "mac_loc"] = self.ct.itunes_link_loc[0]
        else:
            self.playlists_df.loc[index_track, "level"] = -2 if upgrade else -1
            self.playlists_df.loc[index_track, "color"] = "darkgreen"

        self.save_playlists_df()
        self.list_selected("change link")
        if hasattr(self.itunes_tags, 'window'): self.itunes_tags.window.destroy()
        self.audio_selected(None)
        
    def add_hashtag_to_list(self):
        if self.lm.folder_list_selected[0] != "LOCAL": 
            messagebox.showwarning(message="It's not a local list", title="Warning")
            return
        list_df = self.lm.selected_list_df
        hashtag = tkinter.simpledialog.askstring(title="Add Hashtag", prompt="Hashtag to add all tracks list:")
        hashtag = "#" + hashtag
        
        def add_hashtag_to_pathfiles(hashtag, iterable):
            for trackpath in iterable:
                audio = AudioFile(trackpath)
                if not hashtag in audio.comments:
                    audio.comments = audio.comments + " " + hashtag
                    audio.comments = format_spaces(audio.comments)
                    audio.save()
        
        add_hashtag_to_pathfiles(hashtag, list_df.pc_loc)
                
        msg = "Do you want to add it to linked remote files?"
        remote_add = yesno_to_bool(messagebox.askquestion(message=msg, title="Question"))
        
        if remote_add: 
            trackpaths_l = []
            for row in list_df.itertuples():
                if row.linked: trackpaths_l.append(row.mac_pc_loc)
            
            add_hashtag_to_pathfiles(hashtag, trackpaths_l)
                
#     def del_hashtag_from_list(self):
#         #funció a la que passant un unique ens retorna els uniques sota un pattern
#         def uniques(column, pattern, genre=None):
#             if genre == None:
#                 data = it.tracks_df[column].unique()
#             else:
#                 data = it.tracks_df[it.tracks_df.Genre == genre]
#                 data = data[column].unique()
#             matches = []
#             for value in data:
#                 found = re.findall(pattern, value)
#                 matches = matches + found
#                 matches = set(matches)
#                 matches = list(matches)
#             return matches
        
        
#         #hashtags unics
#         pattern = r"\#\S+"
#         data = uniques("Comments", pattern)
#         data.sort()
#         data
        
#----------------------------------NAVIGATOR FUNCTIONS-------------------------------------
    def delete_audio_tree(self, lista=False, folder=False):
        for song in self.audio_list.get_children():
            self.audio_list.delete(song)
        if not lista: return
        for lista in self.list_list.get_children():
            self.list_list.delete(lista)
        if not folder: return
        for folder in self.folder_list.get_children():
            self.folder_list.delete(folder)
            
    def remove_all_widgets(self):
        self.remove_list_btn.grid_remove()
        self.refresh_list_btn.grid_remove()
        self.sort_cb.grid_remove()
        self.origin_route_cb.grid_remove()
        self.list_btn1.grid_remove()
        self.list_btn2.grid_remove()
        self.list_btn3.grid_remove()
# ----------
    def build_tree_browser_from_playlists(self):
        folders = self.playlists_df.Folder.unique()
        #omplim llista folders
        for folder, folder_iid in zip(folders, range(len(folders))):
            if folder == "LOCAL": folder_type = "Local"
            else: folder_type = "Remote"
            self.folder_list.insert("", tk.END, text=folder, iid=folder_iid, tags=("selected", folder_type))
        self.folder_list.tag_configure('Local', foreground='red')
        self.folder_list.tag_configure('Remote', foreground='black')

    def folder_selected(self, event):
        self.delete_audio_tree(lista=True)
        self.remove_all_widgets()
        
        folder_iid = self.folder_list.selection()[0]
        folder = self.folder_list.item(folder_iid, option="text")
        folder_df = self.playlists_df[self.playlists_df.Folder == folder]
        lists = folder_df.List.unique()
        #omplim la llista de llistes
        for lista, list_iid in zip(lists, range(len(lists))):
            if self.playlists_df[self.playlists_df.List == lista].Smart.iat[0]:
                list_type = "Smart"
            else: list_type = "Manual"
            self.list_list.insert("", tk.END, iid=list_iid, text=lista, 
                                  tags=("selected", list_type), values=(folder_iid, folder))
        self.list_list.tag_configure('Smart', foreground='blue')
        self.list_list.tag_configure('Manual', foreground='black')
    
    def list_selected(self, event):
        if not self.enable_trace_vars:return #desabilitem binds
        #si no hi ha cap llista seleccionada retorna
        if not self.list_list.selection(): return
        
        self.delete_audio_tree()
        self.remove_all_widgets()
        
        folder, lista  = self.return_folder_list_selected(return_ids=False)
        
        if type(event) == tk.Event:
            if event.widget.widgetName == 'ttk::treeview':
                self.lm.folder_list_selected = [folder, lista]
            elif event.widget.widgetName == 'ttk::combobox':
                self.lm.sorted_by_cb()
                if self.ct.loaded: self.ct.update() #NO SE SI AQUI ESTIC REDUNDANT L'UPDATE
        else:
            #en el cas que venim d'esborrar track o de refrescar hem de rellegir la llista seleccionada
            if event in ["delete track", "refresh", "change link"]: self.lm.update_selected_list()
            #en el cas de venir d'un afegiment de llista local, o eliminació, ho tractem som una selecció al treeview
            if event in ["add", "delete list"]: self.lm.folder_list_selected = [folder, lista]
            
        list_df = self.lm.selected_list_df

        #si estem a la carpeta "LOCAL" mostrem widgets o sinó sols el d'ordenar
        if folder == "LOCAL":
            self.remove_list_btn.grid(row=0, column=1, padx=2)
            self.refresh_list_btn.grid(row=0, column=2, padx=2)
            self.origin_route_cb.grid(row=0, column=2, padx=2)
            self.list_btn1.grid(row=0, column=3, padx=2)
            self.list_btn2.grid(row=0, column=4, padx=2)
            self.list_btn3.grid(row=0, column=5, padx=2)
        self.sort_cb.grid(row=0, column=0, padx=2)
        
        #omplim audio_list
        artist_s, title_s, level_s = list_df.Artist, list_df.Name, list_df.level
        index_s, location_s, color_s = pd.Series(range(len(list_df))), list_df.Location, list_df.color
        series_zip = zip(artist_s, title_s, level_s, index_s, location_s, color_s)
        for artist, title, level, audio_iid, location, color in series_zip:
            if folder == "LOCAL": level = int(level)
            else: level = ""
            self.audio_list.insert("", tk.END, iid=audio_iid, text=str(audio_iid+1), tags=("selected", color),
                                   values=(artist, title, level, folder, lista, location))
        
        for color in color_s.unique().tolist():
            self.audio_list.tag_configure(color, foreground=color)
        
        self.audio_list.yview_moveto(0)
        
        #si estem al mateix folder/list que el track carregat es selecciona i mostrem amb see() (a audio selected)
        if self.ct.loaded:
            cond1 = self.folder_list.selection()[0] == self.ct.folder_iid
            cond2 = self.list_list.selection()[0] == self.ct.list_iid
            if cond1 & cond2:
                #print("estem al mateix folder/list que el track carregat")
                self.audio_list.selection_set(self.ct.audio_iid)
                
    def audio_selected(self, event):
        audio_iid = self.audio_list.selection()[0]
        v = self.audio_list.item(audio_iid, option="values")
        artist, title, level, folder, lista, location = v[0], v[1], v[2], v[3], v[4], v[5]
        current_track = CurrentTrack(self, folder, lista, location)
        playing_path = current_track.playing_path
        
        #en el cas q seleccionem el mateix track que s'esta reproduint no l'aturarem ni generarem nova instancia
        #a no ser que vinguem de linkar
        if self.ct.loaded:
            if self.media.audio.is_playing():
                if self.media.song_path == playing_path: return
                else: self.media.audio.stop() #si seleccionem qualsevol altre track aturem
        
        #check if file exists
        if not os.path.isfile(playing_path):
            if folder == "LOCAL":
                self.origin_route.set("Local mode")
                msg = f"No connection to {playing_path}.\n'Local mode' work mode changed"
            else: msg = f"No connection to {playing_path}."
            messagebox.showinfo(title="Info", message=msg)    
            return
                
        self.ct = current_track

        #omplim title_song
        self.title_song.set(self.ct.Artist + " - " + self.ct.Name)
        #si treballem amb tot locals establirem el color del title_song en vermell en el cas que l'edició sigui inutil
        if self.ct.linked & (EXPORT_PATH in self.ct.playing_path): #(linkats quan treballem en 'Local mode')
            self.title_song_lbl.configure(fg="red")
        else: self.title_song_lbl.configure(fg="blue")
        
        #omplim etiqueta de ruta
        position = str(int(self.ct.audio_iid) + 1)
        self.route_song.set(folder + "\n" + lista + "\n" +  " (" + position + ")")
            
        self.itunes_tags.fill_itunes_fields()
        self.reader.fill_audio_fields()
        
        if self.reader.autoload.get():
            self.editor.fill_editor_fields()
        
        #fem visible el track en reproducció
        self.audio_list.see(self.ct.audio_iid)
        #carreguem l'art
        image = extract_pic_from_metadata(playing_path, size=(311,311))
        self.label_art.config(image=image)
        self.label_art.image=image
        
        #tanquem la finestra links si esta oberta
        if hasattr(self.itunes_tags, 'window'): self.itunes_tags.window.destroy()
        
        #copiem el artist - title al clipboard
        self.clipboard_clear()
        first_artist = self.ct.Artist.split(";")[0]
        self.clipboard_append(first_artist + " " + self.ct.Name)
        
        #enviem ordre de reproduir al final per deixar temps si hi ha algun thread que ens penja el soft
        self.play_path(playing_path)


        
class CurrentTrack():
    def __init__(self, root, folder=None, lista=None, location=None, loaded=True):
        self.root = root
        self._loaded = loaded
        if not self._loaded: return
        
        self.Folder, self.List = folder, lista
        self.Location = location #location és antic origin_loc (ubicacio desde pc)
        
        if folder == "LOCAL": self.file_origin = "Local"
        else: self.file_origin = "Itunes"
        
        #quan inicialitzem ct s'encarrega de dirli al list manager que la seleccionada es current
        self.root.lm.set_selected_as_current()
        self._fill_track_attributes()
        
        #Location - Ubicació, desde pc local, de l'arxiu amb el que treballarem 
        #           si és d'itunes, ubicació al mac, si es LOCAL ubicació al EXPORT_PATH
        #playing_path - Ubicació de current track (pot ser un LOCAL linkat, local sense linkar, o remot)
    
    @property
    def loaded(self):
        return self._loaded

    @loaded.setter
    def loaded(self, loaded):
        if self._loaded == loaded: return
        self._loaded = loaded
        if not self._loaded: 
            self._delete_track_attributes()
            
    def _fill_track_attributes(self):
        cond = self.root.lm.current_list_df.Location == self.Location
        track_df = self.root.lm.current_list_df[cond]
        self._track_dic = track_df.iloc[0].to_dict()
        
        for attr, value in self._track_dic.items():
            setattr(self, attr, value)
        
        self.itunes_link_loc = [self.mac_loc, self.mac_pc_loc]
        if self.linkable == False: self.linked = False
        
        #si duration es integer(seconds) passem a string
        if type(self.Duration) == int: self.Duration = ms_to_string(self.Duration, metric="seconds")
                
        #si tenim seleccionat l'opció local carreguem la ruta local dels audios, sino la linkada, si n'hi ha
        if (self.file_origin == "Local") & (self.root.origin_route.get() == "Find remotes"):
            self.playing_path = self.mac_pc_loc if self.linked else self.pc_loc
        else: self.playing_path = self.Location #location és ubicacio desde pc (pot estar a mac o a pc)
        
        #posem un playing_origin per si la ruta del paying_path es local o remota d'itunes
        self.playing_origin = "Local" if EXPORT_PATH in self.playing_path else "Itunes"
                
    def update(self):
        self.current_list_df = self.root.lm.selected_list_df
        self._fill_track_attributes()
        
    def _delete_track_attributes(self):
        attributes = list(self.__dict__.keys())
        for attr in attributes:
            delattr(self, attr)
        self._loaded = False
        
              
              
class ListManager():
    def __init__(self, root):
        self.root = root
        self._folder_list_selected = ["Folder", "List"]
        self.folder_list_current = self._folder_list_selected
        self.current_sort_cb = self.root.sortby_cb.get()

    @property
    def folder_list_selected(self):
        return self._folder_list_selected
    
    #llista seleccionada cridada modificant l'atribut per treelist
    #modifican la list selected en el cas que sigui diferent a lanterior seleccionada
    @folder_list_selected.setter
    def folder_list_selected(self, folder_list_selected):
        if folder_list_selected != self._folder_list_selected:
            #print("hem canviat de llista seleccionada")
            self._folder_list_selected = folder_list_selected
            if self._folder_list_selected == self.folder_list_current:
                #print("hem tornat a current llista")
                self.root.enable_trace_vars = False
                self.root.sortby_cb.set(self.current_sort_cb)
                self.root.enable_trace_vars = True
            else:
                sort_by = self.default_list_sort(folder_list_selected)
                self.root.sortby_cb.set(sort_by)
                #print("hem ordenat la llista per", sort_by)
            self.selected_list_df = self.return_list_df(folder_list=folder_list_selected, sort=True, ids=True)    
        #else: print("no hem canviat de llista seleccionada")
    
    #si hem seleccionat un track de la llista seleccionada actual, copia selected_list a current_list
    def set_selected_as_current(self):
        #print("cambiem current list a", self._folder_list_selected)
        self.folder_list_current = self._folder_list_selected
        self.current_sort_cb = self.root.sortby_cb.get()
        self.current_list_df = self.selected_list_df.copy()
            
    #si hem fet un delete track (la llista seleccionada es la mateixa q lactual) 
    def update_selected_list(self):
        self.selected_list_df = self.return_list_df(folder_list=self._folder_list_selected, sort=True, ids=True)
        
    #hem cridat a list_select seleccionant valor al combobox d'ordenacio (la llista seleccionada es la mateixa q lactual)      
    def sorted_by_cb(self):
        self.selected_list_df = self.return_list_df(list_df=self.selected_list_df, sort=True, ids=True)
        #si estem ordenant la llista que sona (current) copiem l'ordenada a current i actualitzem el track
        if self._folder_list_selected == self.folder_list_current:
            self.current_list_df = self.selected_list_df.copy()
            self.current_sort_cb = self.root.sortby_cb.get()
            self.root.ct.update()
    
    #torna la ordenació per defecte de qualsevol llista
    def default_list_sort(self, folder_list_selected):
        if folder_list_selected[0] == "LOCAL":
            list_df = self.return_list_df(folder_list=folder_list_selected)
            if list_df.iloc[0]["Smart"]: return "Position"
        return "Creation (desc.)"
        
    def return_list_df(self, folder_list=None, list_df=None, sort=False, ids=False):
        playlists_df = self.root.playlists_df
        if folder_list != None: 
            list_df_passed = False
            folder, lista = folder_list
            cond1 = playlists_df.Folder == folder
            cond2 = playlists_df.List == lista
            list_df = playlists_df[cond1 & cond2].copy()
        else: list_df_passed = True
        
        if sort:
            sortby, ascending = self.root.sortby_cb.get(), True
            if any([x in self.root.sortby_cb.get() for x in ["Creation", "Modified"]]):
                if "Creation" in self.root.sortby_cb.get(): sortby = "Creation"
                else: sortby = "Date Modified"
                if "(desc.)" in self.root.sortby_cb.get(): ascending = False
            list_df = list_df.sort_values(by=sortby, ascending=ascending)

        if ids:
            if list_df_passed:
                folder = list_df.iloc[0]["Folder"]
                lista = list_df.iloc[0]["List"]
                cond1 = playlists_df.Folder == folder
                cond2 = playlists_df.List == lista

            folders_l = playlists_df.Folder.unique().tolist()
            folder_iid = str(folders_l.index(folder))

            folder_df = playlists_df[cond1]
            lists_l = folder_df.List.unique().tolist()
            list_iid = str(lists_l.index(lista))
       
            #afegim ids
            list_df["folder_iid"] = folder_iid
            list_df["list_iid"] = list_iid
            list_df["audio_iid"] = [str(x) for x in range(len(list_df))]
         
        return list_df   






        
class TagsEditor(tk.Frame):
    def __init__(self, root, parent):      
        self.root = root
        super().__init__(parent)
        self.config(relief='raised', borderwidth=10, bg="#525")
        self.grid(row=0, column=1, rowspan=2, sticky="NSEW")
        #-------------
        self.info_bar = tk.Frame(self, bg="#525")
        self.info_bar.columnconfigure(0, weight=1)
        
        self.origin = tk.StringVar(value="")
        self.origin_lbl = tk.Label(self.info_bar, textvariable=self.origin, bg="#525", fg="white")
        self.editor_status = tk.StringVar(value="EDITOR")
        self.title_edit = tk.Label(self.info_bar, textvariable=self.editor_status, bg="#925", fg="white")
        
        self.origin_lbl.grid(row=0, column=0)
        self.title_edit.grid(row=0, column=1, padx=5, pady=1)
        self.info_bar.pack(fill=tk.BOTH)
        #--------------    
        #estil dels entrys
        color = "black"
        bg = "white"
        font = ("Arial", 13)
        
        edit = "normal"
#---------------------------------------------     
        frame0 = tk.Frame(self, bg="#444")
        frame0.columnconfigure(1, weight=1)
        frame0.pack(padx=5, pady=2, fill=tk.BOTH)
        
        artist_lbl = tk.Label(frame0, text="Artist", font=font, bg="#444", fg="white", width=5)
        self.artist = tk.StringVar(value="")
        self.artist.trace("w", lambda e,f,g: self.user_modification(field="artist"))
        self.artist_e = tk.Entry(frame0, textvariable=self.artist, font=font, bg=bg, fg="blue", state=edit)
        
        title_lbl = tk.Label(frame0, text="Title", font=font, bg="#444", fg="white", width=5, relief=tk.SOLID)
        self.title = tk.StringVar(value="")
        self.title.trace("w", lambda e,f,g: self.user_modification(field="title"))
        self.title_e = tk.Entry(frame0, textvariable=self.title, font=font, bg=bg, fg="blue", state=edit)
        
        artist_lbl.grid(row=0, column=0, sticky="NSEW")
        self.artist_e.grid(row=0, column=1, sticky="NSEW")
        title_lbl.grid(row=1, column=0, sticky="NSEW")
        self.title_e.grid(row=1, column=1, sticky="NSEW")
#---------------------------------------------          
        frame1 = tk.Frame(self, bg="#444")
        frame1.columnconfigure(2, weight=1)
        frame1.pack(padx=5, pady=2, fill=tk.BOTH)
        
        year_lbl = tk.Label(frame1, text="Year", bg="#444", fg="white")
        self.year = tk.StringVar(value="")
        self.year.trace("w", lambda e,f,g: self.user_modification(field="year"))
        self.year_e = tk.Entry(frame1, textvariable=self.year, font=font, bg=bg, fg=color, width=7, relief=tk.SOLID, state=edit)
        
        duration_lbl = tk.Label(frame1, text="Duration", bg="#444", fg="white")
        self.duration = tk.StringVar(value="")
        duration = tk.Entry(frame1, textvariable=self.duration, font=font, bg=bg, fg=color, width=10, 
                            relief=tk.SOLID, state="disabled")
        
        codec_lbl = tk.Label(frame1, text="Codec", bg="#444", fg="white")
        self.codec = tk.StringVar(value="")
        codec = tk.Entry(frame1, textvariable=self.codec, font=font, bg=bg, fg=color, relief=tk.SOLID, state="disabled")
        
        key_lbl = tk.Label(frame1, text="Key", bg="#444", fg="white")
        self.key = tk.StringVar(value="")
        key = tk.Entry(frame1, textvariable=self.key, font=font, bg=bg, fg=color, width=7, relief=tk.SOLID, state="disabled")
        
        bpm_lbl = tk.Label(frame1, text="BPM", bg="#444", fg="white")
        self.bpm = tk.StringVar(value="")
        self.bpm.trace("w", lambda e,f,g: self.user_modification(field="bpm"))
        self.bpm_e = tk.Entry(frame1, textvariable=self.bpm, font=font, bg=bg, fg=color, width=7, relief=tk.SOLID, state=edit)
        
        tracknumber_lbl = tk.Label(frame1, text="My BPM", bg="#444", fg="white")
        self.tracknumber = tk.StringVar(value="")
        self.tracknumber.trace("w", lambda e,f,g: self.user_modification(field="tracknumber"))
        self.tracknumber_e = tk.Entry(frame1, textvariable=self.tracknumber, font=font, bg=bg, fg=color, width=7, 
                                      relief=tk.SOLID, state=edit)
        
        bpm_trans_lbl = tk.Label(frame1, text="Trans.BPM", bg="#444", fg="white")
        self.bpm_trans = tk.StringVar(value="")
        self.bpm_trans.trace("w", lambda e,f,g: self.user_modification(field="bpm_trans"))
        self.bpm_trans_e = tk.Entry(frame1, textvariable=self.bpm_trans, font=font, bg=bg, fg=color, width=7, 
                                    relief=tk.SOLID, state=edit)
        
        bpm_end_lbl = tk.Label(frame1, text="End BPM", bg="#444", fg="white")
        self.bpm_end = tk.StringVar(value="")
        self.bpm_end.trace("w", lambda e,f,g: self.user_modification(field="bpm_end"))
        self.bpm_end_e = tk.Entry(frame1, textvariable=self.bpm_end, font=font, bg=bg, fg=color, width=7, 
                                  relief=tk.SOLID, state=edit)

        year_lbl.grid(row=0, column=0, sticky="NSEW")
        duration_lbl.grid(row=0, column=1, sticky="NSEW")
        codec_lbl.grid(row=0, column=2, sticky="NSEW")
        key_lbl.grid(row=0, column=3, sticky="NSEW")
        bpm_lbl.grid(row=0, column=4, sticky="NSEW")
        tracknumber_lbl.grid(row=0, column=5, sticky="NSEW")
        bpm_trans_lbl.grid(row=0, column=6, sticky="NSEW")
        bpm_end_lbl.grid(row=0, column=7, sticky="NSEW")
        
        self.year_e.grid(row=1, column=0, sticky="NSEW")
        duration.grid(row=1, column=1, sticky="NSEW")
        codec.grid(row=1, column=2, sticky="NSEW")
        key.grid(row=1, column=3, sticky="NSEW")
        self.bpm_e.grid(row=1, column=4, sticky="NSEW")
        self.tracknumber_e.grid(row=1, column=5, sticky="NSEW")
        self.bpm_trans_e.grid(row=1, column=6, sticky="NSEW")
        self.bpm_end_e.grid(row=1, column=7, sticky="NSEW")
#---------------------------------------------          
        frame2 = tk.Frame(self, bg="#444")
        frame2.columnconfigure((0,1,2,3,4), weight=1)
        frame2.pack(padx=5, pady=2, fill=tk.BOTH)
        
        genre_lbl = tk.Label(frame2, text="Genre", bg="#444", fg="white")
        self.genre = tk.StringVar(value="")
        self.genre.trace("w", lambda e,f,g: self.user_modification(field="genre"))
        self.genre_e = tk.Entry(frame2, textvariable=self.genre, font=font, bg=bg, fg=color, relief=tk.SOLID, state=edit)
        
        album_lbl = tk.Label(frame2, text="Subgenres", bg="#444", fg="white")
        self.album = tk.StringVar(value="")
        self.album.trace("w", lambda e,f,g: self.user_modification(field="album"))
        self.album_e = tk.Entry(frame2, textvariable=self.album, font=font, bg=bg, fg=color, relief=tk.SOLID, state=edit)        
        #album.bind('<FocusOut>', self.check_new_subgenres)
   
        self.genre_cb = tk.StringVar(value="Genres")
        self.genres_cb = ttk.Combobox(frame2, textvariable=self.genre_cb, values=[], height=30)
        self.genres_cb.bind('<<ComboboxSelected>>', lambda e: self.cb_selected("genre"))
        
        self.g_subgenre_cb = tk.StringVar(value="Subgenres by Genre")
        self.g_subgenres_cb = ttk.Combobox(frame2, textvariable=self.g_subgenre_cb, values=[], height=30)
        self.g_subgenres_cb.bind('<<ComboboxSelected>>', lambda e: self.cb_selected("g_subgenre"))
        self.g_subgenres_cb.grid(row=2, column=2)
        
        self.subgenre_cb = tk.StringVar(value="All Gubgenres")
        self.subgenres_cb = ttk.Combobox(frame2, textvariable=self.subgenre_cb, values=[], height=30)
        self.subgenres_cb.bind('<<ComboboxSelected>>', lambda e: self.cb_selected("subgenre"))
                
        self.desc_subgen_cb = tk.StringVar(value="Descriptive Subgenres")
        self.desc_subgens_cb = ttk.Combobox(frame2, textvariable=self.desc_subgen_cb, values=[], height=30)
        self.desc_subgens_cb.bind('<<ComboboxSelected>>', lambda e: self.cb_selected("desc_subgen"))
        
        genre_lbl.grid(row=0, column=0, sticky="NSEW")
        album_lbl.grid(row=0, column=1, columnspan=4, sticky="NSEW")
        self.genre_e.grid(row=1, column=0, sticky="NSEW")
        self.album_e.grid(row=1, column=1, columnspan=4, sticky="NSEW")
        self.genres_cb.grid(row=2, column=0)
        self.g_subgenres_cb.grid(row=2, column=2)
        self.subgenres_cb.grid(row=2, column=3)
        self.desc_subgens_cb.grid(row=2, column=4)
        
        subframe2 = tk.Frame(self, bg="#444")
        subframe2.pack(padx=5, pady=2, fill=tk.BOTH)
        
        #muntem a partir de TYPE_SUBGENRE els checkboxs
        for type_subgen in TYPE_SUBGENRE.keys():
            type_subgen_text = type_subgen.capitalize()
            if type_subgen == "alternative": type_subgen_text = type_subgen.capitalize() + " Hit"
            setattr(self, type_subgen, tk.BooleanVar(value=False))
            setattr(self, type_subgen + "_cb", ttk.Checkbutton(subframe2, text=type_subgen_text, 
                                                               variable=getattr(self, type_subgen),
                                                               command=lambda: self.cb_selected("type_subgen")))
            getattr(self, type_subgen + "_cb").pack(side="right")
#---------------------------------------------
        frame3 = tk.Frame(self, bg="#444")
        frame3.columnconfigure((0,1,2,3,4,5), weight=1)
        frame3.pack(padx=5, pady=2, fill=tk.BOTH)
        
        composer_lbl = tk.Label(frame3, text="Rating, Clubs & Generation", bg="#444", fg="white")
        self.composer = tk.StringVar(value="")
        self.composer.trace("w", lambda e,f,g: self.user_modification(field="composer"))
        self.composer_e = tk.Entry(frame3, textvariable=self.composer, font=font, bg=bg, fg=color, relief=tk.SOLID, state=edit)
#         composer.bind('<FocusOut>', self.check_new_clubs_generations)
        
        group_lbl = tk.Label(frame3, text="Group", bg="#444", fg="white")
        self.group = tk.StringVar(value="")
        self.group.trace("w", lambda e,f,g: self.user_modification(field="group"))
        self.group_e = tk.Entry(frame3, textvariable=self.group, font=font, bg=bg, fg=color, relief=tk.SOLID, state=edit)

        self.rating_cb = tk.StringVar(value="Ratings")
        self.ratings_cb = ttk.Combobox(frame3, textvariable=self.rating_cb, values=[])
        self.ratings_cb.bind('<<ComboboxSelected>>', lambda e: self.cb_selected("rating"))
        
        self.like = tk.BooleanVar(value=False)
        self.like_cb = ttk.Checkbutton(frame3, text=HEART, variable=self.like, command=lambda: self.cb_selected("rating"))
        
        self.club_cb = tk.StringVar(value="Clubs")
        self.clubs_cb = ttk.Combobox(frame3, textvariable=self.club_cb, values=[])
        self.clubs_cb.bind('<<ComboboxSelected>>', lambda e: self.cb_selected("club"))
        
        self.generation_cb = tk.StringVar(value="Generations")
        self.generations_cb = ttk.Combobox(frame3, textvariable=self.generation_cb, values=[])
        self.generations_cb.bind('<<ComboboxSelected>>', lambda e: self.cb_selected("generation"))
      
        composer_lbl.grid(row=0, column=0, columnspan=3, sticky="NSEW")
        group_lbl.grid(row=0, column=3, columnspan=3, sticky="NSEW")
        self.composer_e.grid(row=1, column=0, columnspan=3, sticky="NSEW")
        self.group_e.grid(row=1, column=3, columnspan=3, sticky="NSEW")
        self.ratings_cb.grid(row=2, column=0)
        self.like_cb.grid(row=2, column=1)
        self.clubs_cb.grid(row=2, column=2)
        self.generations_cb.grid(row=2, column=3)
#---------------------------------------------  
        frame4 = tk.Frame(self, bg="#444")
        frame4.columnconfigure(0, weight=1)
        frame4.pack(padx=5, pady=2, fill=tk.BOTH)
        
        comments_lbl = tk.Label(frame4, text="Comments", bg="#444", fg="white")
        self.comments = tk.StringVar(value="")
        self.comments.trace("w", lambda e,f,g: self.user_modification(field="comments"))
        self.comments_e = tk.Entry(frame4, textvariable=self.comments, font=font, bg=bg, fg=color, relief=tk.SOLID, state=edit)
        
        self.hashtag = tk.StringVar(value="")
        self.hashtag = tk.Entry(frame4, textvariable=self.hashtag, font=font, bg=bg, fg=color, width=7, relief=tk.SOLID, state=edit)
        hashtag_btn = tk.Button(frame4, text="Add #", relief="raised", borderwidth=0, command=self.add_hashtag)
        
        comments_lbl.grid(row=0, column=0, columnspan=3, sticky="NSEW")
        self.comments_e.grid(row=1, column=0, sticky="NSEW")
        self.hashtag.grid(row=1, column=1, sticky="NSEW")
        hashtag_btn.grid(row=1, column=2, sticky="NSEW")
        
        
        save_btn = tk.Button(self, text="Save Tags", relief="raised", borderwidth=0, command=self.save_audio_tags)
        save_btn.pack(side=tk.RIGHT, padx=5, pady=0)
        
        save_next_btn = tk.Button(self, text="Save & Next", relief="raised", borderwidth=0, 
                                  command=lambda: self.save_audio_tags(True))
        save_next_btn.pack(side=tk.RIGHT, padx=5, pady=0)
        
    def add_hashtag(self):
        comments = self.comments.get()
        hashtag = "#" + self.hashtag.get()
        if not hashtag in comments:
            self.comments.set(format_spaces(comments + " " + hashtag))
    
#USER ENTRY & LOAD TO EDITOR TRACK & MODIFY COMBOX AND CHECKBOX WITH THEM
    def user_modification(self, field="load"):
        #mentre omple els camps desabilitem que entri a la funció
        if not self.enable_trace_vars: return
        
        wo_changes_col = "white"
        to_save_col = "green yellow"
        wrong_col = "pale violet red"
        
        no_format_fields = ["artist", "title", "group", "comments"]
        format_fields = ["year", "genre", "album", "composer", "tracknumber", "bpm"]

        if field == "load":
            self.current_save = {}
            self.current_modified = {key: False for key in format_fields + no_format_fields}
        
        if field in no_format_fields + ["load"]:
            artist = self.artist.get()
            title = self.title.get()
            group = self.group.get()
            comments = self.comments.get()
            
            no_format_fields_dic = dict(zip(no_format_fields, [artist, title, group, comments]))
            for name, value in no_format_fields_dic.items(): 
                self.current_save[name] = value
                self.current_modified[name] = True
            
            if self.editing_audio.artist == artist: 
                self.artist_e.config(bg=wo_changes_col)
                self.current_modified["artist"] = False
            else: self.artist_e.config(bg=to_save_col)
            if self.editing_audio.title == title: 
                self.title_e.config(bg=wo_changes_col)
                self.current_modified["title"] = False
            else: self.title_e.config(bg=to_save_col)
            if self.editing_audio.group == group: 
                self.group_e.config(bg=wo_changes_col)
                self.current_modified["group"] = False
            else: self.group_e.config(bg=to_save_col)
            if self.editing_audio.comments == comments: 
                self.comments_e.config(bg=wo_changes_col)
                self.current_modified["comments"] = False
            else: self.comments_e.config(bg=to_save_col)
        
        if field in ["year", "load"]:
            year = self.year.get()
            self.current_modified["year"] = True
            match = re.match(PATTERN["year"], year)
            if match:
                self.current_save["year"] = year
                if self.editing_audio.date[:4] == year: 
                    self.year_e.config(bg=wo_changes_col)
                    self.current_modified["year"] = False
                else: self.year_e.config(bg=to_save_col)
            else:
                self.current_save["year"] = ""
                self.year_e.config(bg=wrong_col)
                
        if field in ["genre", "load"]:
            genre = self.genre.get()
            self.current_modified["genre"] = True
            match = re.search(PATTERN["genre"], genre)
            if match: genre_l = [match.group()]
            else: genre_l = []
                
            if len(genre_l) == 0: correct = False
            else: correct = self.is_correct(genre, genre_l)["correct"]
            
            if correct:
                self.current_save["genre"] = genre_l[0]
                if self.editing_audio.genre == genre_l[0]: 
                    self.genre_e.config(bg=wo_changes_col)
                    self.current_modified["genre"] = False
                else: self.genre_e.config(bg=to_save_col) 
            else:
                self.current_save["genre"] = genre
                self.genre_e.config(bg=wrong_col)
            
            #modifiquem combobox de genere
            self.genre_cb.set("Genres")
            if len(genre_l) != 0:
                if genre_l[0] in self.root.sub_x_genre_dic.keys(): self.genre_cb.set(genre_l[0])

               
        if field in ["album", "load"]:
            album = self.album.get()
            self.current_modified["album"] = True
            
            subgenres_l, desc_subgenres_l = self.album_fields(album)
            formated_album = " ".join(subgenres_l + desc_subgenres_l)
            
            if self.is_correct(album, subgenres_l + desc_subgenres_l)["correct"]:
                self.current_save["album"] = formated_album
                if self.editing_audio.album == formated_album:
                    self.album_e.config(bg=wo_changes_col)
                    self.current_modified["album"] = False
                else: self.album_e.config(bg=to_save_col)
            else:
                self.current_save["album"] = album
                self.album_e.config(bg=wrong_col)
                
            #modifiquem chekboxes de type_subgens:
            for type_subgen, value in TYPE_SUBGENRE.items():
                if value in desc_subgenres_l: getattr(self, type_subgen).set(True)
                else: getattr(self, type_subgen).set(False)
            

        if field in ["composer", "load"]:
            composer = self.composer.get()
            self.current_modified["composer"] = True
            
            rating_l, clubs_l, generation_l = self.composer_fields(composer)
            formated_composer = " ".join(rating_l + clubs_l + generation_l)
            
            correct = self.is_correct(composer, rating_l + clubs_l + generation_l)["correct"]
            if correct & (len(rating_l) != 0):
                self.current_save["composer"] = formated_composer
                if self.editing_audio.composer == formated_composer:
                    self.composer_e.config(bg=wo_changes_col)
                    self.current_modified["composer"] = False
                else: self.composer_e.config(bg=to_save_col)
            else:
                self.current_save["composer"] = composer
                self.composer_e.config(bg=wrong_col)
                
            #modifiquem combobox i chekbox de rating
            if len(rating_l) != 0:
                rating = rating_l[0]
                p = False
                if "p" in rating: 
                    p = True
                    rating = rating.replace("p", "")
                self.rating_cb.set(key_from_value(RATING, rating))
                self.like.set(p)
            else:
                self.rating_cb.set("Ratings")
                self.like.set(False)
                
            #modifiquem combobox de generation
            if len(generation_l) != 0:
                generation = GENERATION[generation_l[0]]
                self.generation_cb.set(generation)
            else: self.generation_cb.set("Generations") 
        
        refill_tracknumber = False
        if field in ["tracknumber", "bpm", "load"]:
            tracknumber, bpm = self.tracknumber.get(), self.bpm.get()
            self.current_modified["tracknumber"], self.current_modified["bpm"] = True, True
            match_tn, match_bpm = re.match(PATTERN["bpm"], tracknumber), re.match(PATTERN["bpm"], bpm)
            
            if match_bpm:
                bpm_match = True
                self.current_save["bpm"] = bpm
                if self.editing_audio.bpm == bpm: 
                    self.bpm_e.config(bg=wo_changes_col)
                    self.current_modified["bpm"] = False
                else: self.bpm_e.config(bg=to_save_col)
            else:
                bpm_match = False
                self.current_save["bpm"] = ""
                self.bpm_e.config(bg=wrong_col)
                
            if match_tn:
                self.current_save["tracknumber"] = tracknumber
                if self.editing_audio.tracknumber == tracknumber: 
                    self.tracknumber_e.config(bg=wo_changes_col)
                    self.current_modified["tracknumber"] = False
                    #en el cas que els dos facin match i siguin diferents (no múltiples) ho indicarem amb un color especific
                    if not bpms_iguals_o_multiples(bpm, tracknumber, ret_multiple=True):
                        self.tracknumber_e.config(bg="azure")
                    
                else: 
                    self.tracknumber_e.config(bg=to_save_col)
                    #en el cas que tinguin diferencia més petita que 2 posarem bpm a tracknumber
                    if bpms_iguals_o_multiples(bpm, tracknumber, ret_igual=True):
                        self.current_save["tracknumber"] = bpm
                        refill_tracknumber = True    
                        self.tracknumber_e.config(bg=to_save_col)
            else:
                if (field in ["bpm", "load"]) & bpm_match:
                    self.current_save["tracknumber"] = bpm
                    refill_tracknumber = True
                    self.tracknumber_e.config(bg=to_save_col)
                else:
                    self.current_save["tracknumber"] = ""
                    self.tracknumber_e.config(bg=wrong_col)
        
        #si hi ha algun valor modificat posem a editing, sino a saved
        if any(list(self.current_modified.values())):
            self.editor_status.set("EDITING")
            self.title_edit.config(bg="green yellow", fg="black")
        else:
            self.editor_status.set("SAVED")
            self.title_edit.config(bg="green", fg="black")
            
        #Si ha modificat tracknumber, finalment, per no creuar events,doncs provocará un callback de escitura 
        #sobre tracknumber, ubiquem el nou tracknumber extret de bpm a self.tracknumber
        if refill_tracknumber: self.tracknumber.set(self.current_save["tracknumber"])
            
#FORMAT FUNCTIONS
    def is_correct(self, tag, fields_l):
        other = tag
        for value in fields_l: other = other.replace(value, "")
        wrong = ' '.join(other.split())
        other = other.replace(" ","")
        if other == "": correct = True
        else: correct = False
            
        return {"correct": correct, "wrong_text":wrong}

    def album_fields(self, album, wrong_text=False):
        subgenres_l = re.findall(PATTERN["subgenre"], album)
        desc_subgenres_l = re.findall(PATTERN["desc_subgenre"], album)
        
        if not wrong_text: return subgenres_l, desc_subgenres_l
        else:
            wrong_text = self.is_correct(album, subgenres_l + desc_subgenres_l)["wrong_text"]
            return subgenres_l, desc_subgenres_l, wrong_text
    
    def composer_fields(self, composer, wrong_text=False):
        rating_match = re.search(PATTERN["rating"], composer)
        if rating_match: rating_l = [rating_match.group()]
        else: rating_l = []
        clubs_l = re.findall(PATTERN["club"], composer)
        generation_match = re.search(PATTERN["generation"], composer)
        if generation_match: generation_l = [generation_match.group()]
        else: generation_l = []

        if not wrong_text: return rating_l, clubs_l, generation_l
        else:
            wrong_text = self.is_correct(composer, rating_l + clubs_l + generation_l)["wrong_text"]
            return rating_l, clubs_l, generation_l, wrong_text
        
        
#EASY TAGS SELECTED
    def cb_selected(self, cb):
        if not self.root.ct.loaded: return
        
        if cb == "genre":
            genre = self.genre_cb.get()
            self.genre.set(genre)
            subgenres = self.root.sub_x_genre_dic[genre]
            self.g_subgenres_cb.config(values=subgenres)
            other_subgenres = [subgen for subgen in self.root.subgenres_l if subgen not in subgenres]
            self.subgenres_cb.config(values=other_subgenres)
            
        if cb == "g_subgenre": subgenre = self.g_subgenre_cb.get()
        elif cb == "subgenre": subgenre = self.subgenre_cb.get()
        elif cb == "desc_subgen": subgenre = key_from_value(self.root.desc_subgen_dic, self.desc_subgen_cb.get())

        if cb in ["g_subgenre", "subgenre", "desc_subgen"]:
            album = self.album.get()
            if subgenre in album: return
            subgenres_l, desc_subgenres_l, wrong_text = self.album_fields(album, wrong_text=True)
            if cb in ["g_subgenre", "subgenre"]: subgenres_l.append(subgenre)
            elif cb == "desc_subgen": desc_subgenres_l.append(subgenre)
            self.album.set(" ".join(subgenres_l + desc_subgenres_l + [wrong_text]))
                 
        if cb == "type_subgen":
            album = self.album.get()
            subgenres_l, desc_subgenres_l, wrong_text = self.album_fields(album, wrong_text=True)
            for type_subgen, value in TYPE_SUBGENRE.items():
                checked = getattr(self, type_subgen).get()
                if checked & (value not in desc_subgenres_l):
                    desc_subgenres_l.append(value)
                elif (not checked) & (value in desc_subgenres_l):
                    desc_subgenres_l.remove(value)
            self.album.set(" ".join(subgenres_l + desc_subgenres_l + [wrong_text]))
        
        if cb == "rating":
            rating = RATING[self.rating_cb.get()]
            p = self.like.get()
            if p: rating = rating[:-1] + "p" + rating[-1:]
            if rating == "*p": rating = 'zp'
            composer_add = rating
        elif cb == "club": composer_add = self.club_cb.get()
        elif cb == "generation": composer_add = key_from_value(GENERATION, self.generation_cb.get())    
        if cb in ["rating", "club", "generation"]:
            composer = self.composer.get()
            if composer_add in composer: return
            rating_l, clubs_l, generation_l, wrong_text = self.composer_fields(composer, wrong_text=True)
            if cb == "rating": rating_l = [composer_add]
            elif cb == "club": clubs_l.append(composer_add)
            elif cb == "generation": generation_l = [composer_add]
            self.composer.set(" ".join(rating_l + clubs_l + generation_l + [wrong_text]))

#definim un patch per convertir a majúscules la generation doncs antigament ho guardavem en minúscules
    def composer_generation_patched(self, composer):
        generation_l = re.findall(r"\B\:\w\b", composer)
        if len(generation_l) != 0:
            composer = composer.replace(generation_l[0], generation_l[0].upper())
        return composer
        
#TAG EDITOR FUNCTIONS
    def fill_editor_fields(self, playing_path=None):
        if not self.root.ct.loaded: return
        
        if playing_path == None: playing_path = self.root.ct.playing_path
        
        if EXPORT_PATH in self.root.ct.playing_path: #origin = "PC"
            self.origin.set("LOCAL")
            if self.root.ct.linked: #(linkats quan treballem en 'Local mode')
                self.config(bg="#999")
                self.info_bar.config(bg="#999")
                self.origin_lbl.config(bg="#999")
            else: 
                self.config( bg="#525")
                self.info_bar.config(bg="#525")
                self.origin_lbl.config(bg="#525")
        else: #origin = "MAC" 
            self.origin.set("REMOTE")
            self.config(bg="#525")
            self.info_bar.config(bg="#525")
            self.origin_lbl.config(bg="#525")
        
        
        self.enable_trace_vars = False
        
        editing_audio = AudioFile(playing_path)
        self.editing_audio = AudioFile(playing_path)
        
        #afegirem als diccionaris de uniques si els tags porten data no actualitzada a itunes
        self.append_new_uniques(genre=editing_audio.genre, album=editing_audio.album, composer=editing_audio.composer)
        
        self.artist.set(editing_audio.artist)
        self.title.set(editing_audio.title)
        self.year.set(editing_audio.date[:4])
        self.duration.set(editing_audio.duration)
        self.codec.set(editing_audio.codec)
        self.genre.set(editing_audio.genre)
        self.genres_cb.config(values=list(self.root.sub_x_genre_dic.keys()))
        
        self.album.set(editing_audio.album)
        self.g_subgenre_cb.set("Subgenres of Genre")
        if editing_audio.genre in self.root.sub_x_genre_dic.keys():
            subgenres = self.root.sub_x_genre_dic[editing_audio.genre]
        else: subgenres = []
        self.g_subgenres_cb.config(values=subgenres)
        self.subgenre_cb.set("Other Subgenres")
        other_subgenres = [subgen for subgen in self.root.subgenres_l if subgen not in subgenres]
        self.subgenres_cb.config(values=other_subgenres)
        self.desc_subgen_cb.set("Descriptive Subgenres")
        self.desc_subgens_cb.config(values=list(self.root.desc_subgen_dic.values()))
        
        self.composer.set(self.composer_generation_patched(editing_audio.composer))
        self.ratings_cb.config(values=list(RATING.keys()))
        #self.rating_to_cb()
        self.club_cb.set("Clubs")
        self.clubs_cb.config(values=self.root.clubs_l)
        self.generations_cb.config(values=list(GENERATION.values()))
        
        self.group.set(editing_audio.group)
        self.key.set(editing_audio.key)
        self.tracknumber.set(editing_audio.tracknumber)
        self.bpm.set(editing_audio.bpm)
        self.comments.set(editing_audio.comments)
        
        
        self.enable_trace_vars = True
        self.user_modification(field="load")
        
#SAVE FUNCTIONS (append_new_uniques porta un patch per actualitzar uniques al carregar el tema)     
    def append_new_uniques(self, current_save=None, current_modified=None, **kwargs):
        if (current_save == None) | (current_modified == None):
            tags = ["genre", "album", "composer"]
            current_modified, current_save = {}, {}
            for tag in tags:
                current_modified[tag] = True
                current_save[tag] = kwargs[tag]
        
        #géneres, subgéneres i subgéneres descriptius
        if current_modified["genre"] | current_modified["album"]:
            genre = current_save["genre"]
            album = current_save["album"]
            
            match = re.search(PATTERN["genre"], genre)
            
            genre_match = False
            if match:
                genre_match = True
                genre = match.group()
                if genre not in self.root.sub_x_genre_dic.keys():
                    self.root.sub_x_genre_dic[genre] = []
                    self.root.sub_x_genre_dic = dict(sorted(self.root.sub_x_genre_dic.items()))
            
            subgenres_l = re.findall(PATTERN["subgenre"], album)
            for subgenre in subgenres_l:
                if subgenre not in self.root.subgenres_l:
                    self.root.subgenres_l.append(subgenre)
                    self.root.subgenres_l.sort()
                if genre_match: 
                    subgen_x_gen_l = self.root.sub_x_genre_dic[genre]
                    if subgenre not in subgen_x_gen_l:
                        self.root.sub_x_genre_dic[genre].append(subgenre)
                        self.root.sub_x_genre_dic[genre].sort()
                    
            type_subgenres_l = list(TYPE_SUBGENRE.values())
            desc_subgenres_l = list(self.root.desc_subgen_dic.keys())
            album_desc_subgenres_l = re.findall(PATTERN["desc_subgenre"], album)
            for desc_subgenre in album_desc_subgenres_l:
                if desc_subgenre not in desc_subgenres_l + type_subgenres_l:
                    self.root.desc_subgen_dic[desc_subgenre] = desc_subgenre

        #clubs                
        if current_modified["composer"]:
            composer = current_save["composer"]
            clubs_l = re.findall(PATTERN["club"], composer)
            for club in clubs_l:
                if club not in self.root.clubs_l:
                    self.clubs_l.append(club)
                    self.root.clubs_l.sort()
            

    def save_audio_tags(self, play_next=False):
        if self.editor_status.get() == "EDITOR": return
        if play_next: self.root.media.audio.stop()#si posem l'stop prop del change, es penja (??)

        #agafem a variables locals les que impliquen al desament del track
        saving_audio = self.editing_audio
        #playing_path = saving_audio.filepath
        current_save = self.current_save
        current_modified = self.current_modified
            
        tags = ["artist", "title", "year", "genre", "album", "group", "composer", "tracknumber", "bpm", "comments"]
        for tag in tags:
            if tag == "year": attr = "date"
            else: attr = tag
            if current_modified[tag]: setattr(saving_audio, attr, current_save[tag])
            
        saved = saving_audio.save()
        
        self.append_new_uniques(current_save, current_modified)
        
        if play_next: self.root.change_song(1)
        else:
            #tornem a rellegir la metadata
            self.root.reader.fill_audio_fields()

            self.fill_editor_fields()



class TagsReader(tk.Frame):
    def __init__(self, root, parent, frame, location_width=85):      
        self.root = root
        
        super().__init__(parent)
        self.config(relief='raised', borderwidth=10, bg="#999")
        self.pack(fill=tk.BOTH, expand=1)

        if frame == "Itunes":
            itunes_bar = tk.Frame(self, bg="#999")
            itunes_bar.columnconfigure(1, weight=1)
            
            #-------------
            self.link_frame = tk.Frame(itunes_bar)
            self.select_link_btn = tk.Button(self.link_frame, text="Linkables", command=self.select_linkable)
            self.link_btn = tk.Button(self.link_frame, text="Link", command=lambda: self.root.change_link(True))
            self.unlink_btn = tk.Button(self.link_frame, text="Unlink", command=lambda: self.root.change_link(False))
            self.upgrade_btn = tk.Button(self.link_frame, text="Upgrade", command=self.root.upgrade_track)
            self.select_link_btn.grid(row=0, column=0, padx=0)
            self.link_btn.grid(row=0, column=1, padx=0)
            self.unlink_btn.grid(row=0, column=2, padx=0)
            self.upgrade_btn.grid(row=0, column=3, padx=2)
            #--------------
            self.info_link = tk.StringVar(value="")
            info_link_lbl = tk.Label(itunes_bar, textvariable=self.info_link, bg="#999", fg="white")
            
            self.play_btn = tk.Button(itunes_bar, text="Play", 
                                command=lambda: self.root.play_path(prelisten="button"))
            title_read = tk.Label(itunes_bar, text="ITUNES", bg="#925", fg="white")
            
            self.link_frame.grid(row=0, column=0, padx=2)
            info_link_lbl.grid(row=0, column=1)
            self.play_btn.grid(row=0, column=2, padx=2)
            title_read.grid(row=0, column=3, padx=5)
            
            itunes_bar.pack(fill=tk.BOTH)
            
            self.remove_itunes_widgets()
            
            
        elif frame == "Metadata":
            title_read = tk.Label(self, text="METADATA", bg="#925", fg="white")
            title_read.pack(anchor=tk.NE, padx=5, pady=2)
        
        color = "black"
        bg = "white"
        font = ("Arial", 12)
        edit = "disabled"
        
        info_frame = tk.Frame(self, bg="#044")
        info_frame.columnconfigure(1, weight=1)
        info_frame.pack(padx=5, pady=2, fill=tk.BOTH)
        
        artist_lbl = tk.Label(info_frame, text="Artist", font=font, bg="#044", fg="white", width=5)
        self.artist = tk.StringVar(value="")
        artist = tk.Entry(info_frame, textvariable=self.artist, font=font, bg=bg, fg="blue", state=edit)
        
        title_lbl = tk.Label(info_frame, text="Title", font=font, bg="#044", fg="white", width=5, relief=tk.SOLID)
        self.title = tk.StringVar(value="")
        title = tk.Entry(info_frame, textvariable=self.title, font=font, bg=bg, fg="blue", state=edit)
        
        year_lbl = tk.Label(info_frame, text="Year", font=font, bg="#044", fg="white")
        self.year = tk.StringVar(value="")
        year = tk.Entry(info_frame, textvariable=self.year, font=font, bg=bg, fg=color, width=9, relief=tk.SOLID, state=edit)
        
        duration_lbl = tk.Label(info_frame, text="Duration", font=font, bg="#044", fg="white")
        self.duration = tk.StringVar(value="")
        duration = tk.Entry(info_frame, textvariable=self.duration, font=font, bg=bg, fg=color, width=8, relief=tk.SOLID, state=edit)
        
        codec_lbl = tk.Label(info_frame, text="Codec", font=font, bg="#044", fg="white")
        self.codec = tk.StringVar(value="")
        codec = tk.Entry(info_frame, textvariable=self.codec, font=font, bg=bg, fg=color, width=9, relief=tk.SOLID, state=edit)
        
        artist_lbl.grid(row=0, column=0, sticky="NSEW")
        title_lbl.grid(row=1, column=0, sticky="NSEW")
        year_lbl.grid(row=0, column=2, sticky="NSEW")
        duration_lbl.grid(row=0, column=3, sticky="NSEW")
        codec_lbl.grid(row=0, column=4, sticky="NSEW")
         
        artist.grid(row=0, column=1, sticky="NSEW")
        title.grid(row=1, column=1, sticky="NSEW")
        year.grid(row=1, column=2, sticky="NSEW")
        duration.grid(row=1, column=3, sticky="NSEW")
        codec.grid(row=1, column=4, sticky="NSEW")
        
        if frame == "Itunes": var_column = 2
        elif frame == "Metadata": var_column = 1
        frame1 = tk.Frame(self, bg="#044")
        frame1.columnconfigure(var_column, weight=1)
        frame1.pack(padx=5, fill=tk.BOTH)
        
        if frame == "Itunes": width_genre, width_group = 25, 18
        elif frame == "Metadata": width_genre, width_group = 30, 23
        
        if frame == "Itunes":
            rating_lbl = tk.Label(frame1, text="Rating", bg="#044", fg="white")
            self.rating = tk.StringVar(value="")
            rating = tk.Entry(frame1, textvariable=self.rating, font=font, bg=bg, fg=color, width=10, relief=tk.SOLID, state=edit)
        
        genre_lbl = tk.Label(frame1, text="Genre", bg="#044", fg="white")
        self.genre = tk.StringVar(value="")
        genre = tk.Entry(frame1, textvariable=self.genre, font=font, bg=bg, fg=color, width=width_genre, relief=tk.SOLID, state=edit)
        
        album_lbl = tk.Label(frame1, text="Album", bg="#044", fg="white")
        self.album = tk.StringVar(value="")
        album = tk.Entry(frame1, textvariable=self.album, font=font, bg=bg, fg=color, relief=tk.SOLID, state=edit)
        
        group_lbl = tk.Label(frame1, text="Group", bg="#044", fg="white")
        self.group = tk.StringVar(value="")
        group = tk.Entry(frame1, textvariable=self.group, font=font, bg=bg, fg=color, width=width_group, relief=tk.SOLID, state=edit)
        
        if frame == "Itunes": 
            rating_lbl.grid(row=0, column=0, sticky="NSEW")
            offset = 1
        elif frame == "Metadata": offset = 0
        
        genre_lbl.grid(row=0, column=0+offset, sticky="NSEW")
        album_lbl.grid(row=0, column=1+offset, sticky="NSEW")
        group_lbl.grid(row=0, column=2+offset, sticky="NSEW")
        
        if frame == "Itunes": rating.grid(row=1, column=0, sticky="NSEW")   
        genre.grid(row=1, column=0+offset, sticky="NSEW")
        album.grid(row=1, column=1+offset, sticky="NSEW")
        group.grid(row=1, column=2+offset, sticky="NSEW")
        
        
        frame2 = tk.Frame(self, bg="#044")
        frame2.columnconfigure(0, weight=1)
        frame2.pack(padx=5, fill=tk.BOTH)
        
        if frame == "Itunes":
            added_lbl = tk.Label(frame2, text="Added", bg="#044", fg="white")
            self.added = tk.StringVar(value="")
            added = tk.Entry(frame2, textvariable=self.added, font=font, bg=bg, fg=color, width=11, relief=tk.SOLID, state=edit)
        
        composer_lbl = tk.Label(frame2, text="Composer", bg="#044", fg="white")
        self.composer = tk.StringVar(value="")
        composer = tk.Entry(frame2, textvariable=self.composer, font=font, bg=bg, fg=color, relief=tk.SOLID, state=edit)
        
        key_lbl = tk.Label(frame2, text="Key", bg="#044", fg="white")
        self.key = tk.StringVar(value="")
        key = tk.Entry(frame2, textvariable=self.key, font=font, bg=bg, fg=color, width=5, relief=tk.SOLID, state=edit)
        
        tracknumber_lbl = tk.Label(frame2, text="Track No", bg="#044", fg="white")
        self.tracknumber = tk.StringVar(value="")
        tracknumber = tk.Entry(frame2, textvariable=self.tracknumber, font=font, bg=bg, fg=color, width=6, relief=tk.SOLID, state=edit)
        
        bpm_lbl = tk.Label(frame2, text="BPM", bg="#044", fg="white")
        self.bpm = tk.StringVar(value="")
        bpm = tk.Entry(frame2, textvariable=self.bpm, font=font, bg=bg, fg="white", width=6, relief=tk.SOLID, state=edit)
        
        if frame == "Itunes": width= 30
        elif frame == "Metadata": width= 41
        comments_lbl = tk.Label(frame2, text="Commentaris", bg="#044", fg="white")
        self.comments = tk.StringVar(value="")
        comments = tk.Entry(frame2, textvariable=self.comments, font=font, bg=bg, fg=color, width=width, relief=tk.SOLID, state=edit)
        
        composer_lbl.grid(row=0, column=0, sticky="NSEW")
        key_lbl.grid(row=0, column=1, sticky="NSEW")
        tracknumber_lbl.grid(row=0, column=2, sticky="NSEW")
        bpm_lbl.grid(row=0, column=3, sticky="NSEW")
        comments_lbl.grid(row=0, column=4, sticky="NSEW")
         
        composer.grid(row=1, column=0, sticky="NSEW")
        key.grid(row=1, column=1, sticky="NSEW")
        tracknumber.grid(row=1, column=2, sticky="NSEW")
        bpm.grid(row=1, column=3, sticky="NSEW")
        comments.grid(row=1, column=4, sticky="NSEW")
        
        frame3 = tk.Frame(self, bg="#044")
        frame3.columnconfigure(1, weight=1)
        
        location_lbl = tk.Label(frame3, text="Location", font=font, bg="black", fg="white")
        self.location = tk.StringVar(value="")
        location = tk.Entry(frame3, textvariable=self.location, font=font, bg="black", fg="white", width=location_width, relief=tk.SOLID, state=edit)
        
        if frame == "Itunes":
            added_lbl.grid(row=0, column=5)
            added.grid(row=1, column=5)
            
        elif frame == "Metadata":
            frame3.pack(pady=5, padx=20, fill=tk.X)
            location_lbl.grid(row=0, column=0)
            location.grid(row=0, column=1, sticky="EW")
            
            self.delete_btn = tk.Button(self, text="Delete File", relief="raised", borderwidth=5, command=self.root.delete_track)
            self.later_btn = tk.Button(self, text="Later", relief="raised", borderwidth=5, command=lambda: self.root.delete_track(later=True))
            self.delete_btn.pack(side=tk.LEFT, padx=5, pady=2)
            self.later_btn.pack(side=tk.LEFT, padx=5, pady=2)
            
            self.autoload = tk.BooleanVar(self, value=True)
            autoload_cb = ttk.Checkbutton(self, text="Auto-load to edit", variable=self.autoload)
#             autoload_cb.grid(row=0, column=5, rowspan=2, padx=3)
            autoload_cb.pack(side=tk.RIGHT, padx=5, pady=2)
            
            load_btn = tk.Button(self, text="Edit", relief="raised", borderwidth=5, 
                            command=self.root.editor.fill_editor_fields)
#             btn.grid(row=0, column=6, rowspan=2, padx=3)
            load_btn.pack(side=tk.RIGHT, padx=5, pady=2)
    
    
    
    
    def remove_itunes_widgets(self):
        for widgets in self.link_frame.winfo_children():
            widgets.grid_remove()
        self.link_frame.grid_remove()
        self.play_btn.grid_remove()
        
    def audio_selected(self, event):
        audio_iid = self.audio_list.selection()[0]
        v = self.audio_list.item(audio_iid, option="values")
        artist, title, duration, level, mac_pc_loc, mac_loc = v[0], v[1], v[2], v[3], v[4], v[5]
        
        self.root.ct.itunes_link_loc = [mac_loc, mac_pc_loc]
        
        self.fill_itunes_fields(prelisten=True)
        self.root.play_path(prelisten="select")

    def select_linkable(self):
        self.window = tk.Toplevel()
        self.window.title("Linkables")
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        self.window.geometry("+%d+%d" %(x+30,y+570))
        self.window.wm_transient(self.root)

        self.audio_list = ttk.Treeview(self.window, height=13, columns=("artist", "title", "duration", "level"), selectmode="browse")
        self.audio_list.tag_bind("selected", "<<TreeviewSelect>>", self.audio_selected)
        self.audio_list_sb = ttk.Scrollbar(self.window, orient="vertical", command=self.audio_list.yview)
        self.audio_list.configure(yscrollcommand=self.audio_list_sb.set)
        self.audio_list.heading("#0", text="Nº")
        self.audio_list.column("#0", minwidth=0, width=41, stretch=tk.NO)
        self.audio_list.heading("artist", text="Artist")
        self.audio_list.column("artist", minwidth=0, width=250, stretch=tk.NO)
        self.audio_list.heading("title", text="Title")
        self.audio_list.column("title", minwidth=0, width=449, stretch=tk.NO)
        self.audio_list.heading("duration", text="Title")
        self.audio_list.column("duration", minwidth=0, width=100, stretch=tk.NO)
        self.audio_list.heading("level", text="L")
        self.audio_list.column("level", minwidth=0, width=25, stretch=tk.NO)

        self.audio_list.grid(row=0, column=0)
        self.audio_list_sb.grid(row=0, column=1, sticky="nse")

        #omplim audio_list
        list_df = self.root.linker.build_track_in_library_df(self.root.ct.Location, all_linkables=True)
        artist_s, title_s, duration_s, level_s = list_df.Artist, list_df.Name, list_df.Duration, list_df.level
        index_s, mac_pc_loc_s, mac_loc_s = pd.Series(range(len(list_df))), list_df.mac_pc_loc, list_df.mac_loc
        series_zip = zip(index_s, artist_s, title_s, duration_s, level_s, mac_pc_loc_s, mac_loc_s)
        for audio_iid, artist, title, duration, level, mac_pc_loc, mac_loc in series_zip:
            self.audio_list.insert("", tk.END, iid=audio_iid, text=str(audio_iid+1), tags=("selected"),
                                   values=(artist, title, duration, level, mac_pc_loc, mac_loc))
          

    def fill_itunes_fields(self, prelisten=False):
        self.remove_itunes_widgets()
        
        if self.root.ct.file_origin == "Local":
            if not self.root.ct.linkable:
                self.del_itunes_fields()
                return
                
            self.link_frame.grid(row=0, column=0, padx=2)
            self.select_link_btn.grid(row=0, column=0, padx=0)
            self.link_btn.grid(row=0, column=1, padx=0)
            self.unlink_btn.grid(row=0, column=2, padx=0)
            self.upgrade_btn.grid(row=0, column=3, padx=2)
            self.play_btn.grid(row=0, column=4, padx=2)  

            linked = self.root.ct.linked           
            if prelisten:
                if self.root.ct.itunes_link_loc[1] == self.root.ct.mac_pc_loc:
                    linked = self.root.ct.linked
                else: linked = False
            
            if linked:
                self.info_link.set("LINKED")
                if self.root.ct.itunes_link_loc[1] == self.root.ct.mac_pc_loc:
                    self.link_btn.grid_remove()
            else: 
                self.info_link.set("NO LINKED")  
                self.unlink_btn.grid_remove()
                if self.root.ct.level == -2:#track upgraded
                    self.select_link_btn.grid_remove()
                    self.upgrade_btn.grid_remove()
                    
            if self.root.ct.playing_origin == "Local": #carregat arxiu local
                self.play_btn.config(text="Listen Remote")
            else: #carregat arxiu remot linkable
                self.play_btn.config(text="Listen Local")
        
        file = self.root.ct.itunes_link_loc[1]
        song_s = self.root.tracks_df[self.root.tracks_df["mac_pc_loc"] == file].iloc[0]
        
        added = song_s["Date Added"][:10]
        self.added.set(added[8:] + "/" + added[5:7] + "/" + added[:4])
        self.artist.set(song_s["Artist"])
        self.title.set(song_s["Name"])
        self.year.set(song_s["Year"])
        self.duration.set(song_s["Duration"])
        self.codec.set(song_s["Codec"])
        rate = song_s["Rating"]
        if type(rate) == float: rate = str(int(rate))
        self.rating.set(RATING_IT[rate])
        self.genre.set(song_s["Genre"])
        self.album.set(song_s["Album"])
        self.group.set(song_s["Grouping"])
        self.composer.set(song_s["Composer"])
        self.key.set("---")
        self.tracknumber.set(song_s["Track Number"])
        self.bpm.set(song_s["BPM"])
        self.comments.set(song_s["Comments"])
         
    def fill_audio_fields(self):
        playing_path =  self.root.ct.playing_path
        audio = AudioFile(playing_path)
        
        data_s = audio.data_df().iloc[0]
        self.artist.set(data_s["artist"])
        self.title.set(data_s["title"])
        self.year.set(data_s["date"][:4])
        self.duration.set(data_s["duration"])
        self.codec.set(data_s["codec"])
        self.genre.set(data_s["genre"])
        self.album.set(data_s["album"])
        self.group.set(data_s["group"])
        self.composer.set(data_s["composer"])
        self.key.set(data_s["key"])
        self.tracknumber.set(data_s["tracknumber"])
        self.bpm.set(data_s["bpm"])
        self.comments.set(data_s["comments"])
        self.location.set(playing_path) #no confondre amb Location de root.ct
        
    def del_itunes_fields(self):
        self.added.set("")
        self.artist.set("")
        self.title.set("")
        self.year.set("")
        self.duration.set("")
        self.codec.set("")
        self.rating.set("")
        self.genre.set("")
        self.album.set("")
        self.group.set("")
        self.composer.set("")
        self.key.set("")
        self.tracknumber.set("")
        self.bpm.set("")
        self.comments.set("")
        
        

class MusicPlayer:
    def __init__(self, song_path):
        self.song_path = song_path
        self.audio = vlc.MediaPlayer(self.song_path)
        
    #set position
    def set_position(self, perc):
        self.audio.set_position(perc)
    
    #mostra minut:segon en la reproducció de la cançó
    def playing_time(self):
        sec = self.audio.get_time() / 1000
        m, s = divmod(sec, 60)
        return str(int(m)) + ":" + str(int(s)).zfill(2)
    
    #salta x segons en la reproducció de la canço
    def jump(self, seconds):
        now = self.audio.get_time()
        self.audio.set_time(now + seconds*1000)




