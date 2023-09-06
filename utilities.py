import time
def print_time(text, time0):
    new_time0 = time.time()
    print(text, new_time0 - time0)
    return new_time0

import os, re, threading, mutagen
import pandas as pd
import numpy as np
from urllib.parse import unquote
from PIL import Image, ImageTk
from io import BytesIO
from legoteca import AudioFile


#FUNCIONS PER EXPORTAR PLAYLISIS I INSERTAR LLISTES DE LOCALS AL NAVIGATOR FRAME PER L'APP
#TAMBE SERVIRAN PER CREAR PLAYLISTS D'EXPORTACIÓ A ITUNES

AUDIO_EXT = (".mp3", ".m4a")


def pcmacloc_from_pcloc(pc_loc):
    pc_mac_loc = pc_loc.replace("D:\\MUSIQUE", "/Volumes")
    return pc_mac_loc.replace(os.sep, "/")

def audio_files_in_folder(path, subfolders=False):
    path_df = pd.DataFrame()
    columns = ["root", "folder", "file", "Position", "Length"]
    
    #comprovem si la carpeta te subdirectoris
    dirs_l = [x[0] for x in os.walk(path)]
    if len(dirs_l) < 2: subfolders=False
    
    if subfolders:
        for root, dirs, files in os.walk(path):
            folder = root.split(os.sep)[-1]
            files_l = [f for f in files if f.endswith(AUDIO_EXT)]
            for file, i in zip(files, range(len(files))):
                filepath = root + os.sep + file
                df = pd.DataFrame(data=[[root, folder, file, i, len(files)]], columns=columns)
                path_df = pd.concat([path_df, df], axis=0)
    else:
        folder = path.split(os.sep)[-1]
        files_l = list(os.scandir(path))
        files_l = [f for f in files_l if (f.name.endswith(AUDIO_EXT)) & f.is_file()]
        for file, i in zip(files_l, range(len(files_l))):
            df = pd.DataFrame(data=[[path, folder, file.name, i, len(files_l)]], columns=columns)
            path_df = pd.concat([path_df, df], axis=0)
    
    if path_df.empty: return path_df #si no hi ha res
    
    path_df["pc_loc"] = path_df.root + os.sep + path_df.file
    path_df["loc"] = path_df.pc_loc
    path_df["pc_mac_loc"] = path_df.pc_loc.apply(pcmacloc_from_pcloc)
    path_df["Codec"] = path_df.pc_loc.apply(lambda x: "MP3" if x.split(".")[-1].lower() == "mp3" else "AAC")
    
    #creem un index per poder treballar amb ell
    path_df.reset_index(drop=True, inplace=True)
    
    #mirem per cada folder a importar si hi ha playlist.m3u8 i ordenem aquesta llista amb els temes de la playlist primer
    #i despres amb els que no hi son
    for root in path_df.root.unique().tolist():      
        pl_file = root + os.sep + "playlist.m3u8"
        hay_playlist = os.path.isfile(pl_file)
        if hay_playlist:
            path_df["Smart"] = True
            files_l = path_df[path_df.root == root].file.tolist()
            with open(pl_file, 'r', encoding='utf-8') as pl_text:
                playlist_l = [line.rstrip() for line in pl_text if line.rstrip().endswith(AUDIO_EXT)]
                playlist_l = [unquote(fn) for fn in playlist_l]
            playlist_l = [track for track in playlist_l if track in files_l]
            sort_dic = {track: playlist_l.index(track) for track in playlist_l}
            if bool(sort_dic): max_pos = max(sort_dic.values())
            else: max_pos = -1 #si no hi ha cap track del folder a la playlist
            df = path_df[path_df.root == root].copy()
            not_sort_l = [f for f in files_l if f not in sort_dic.keys()]
            not_sort_dic = dict(zip(not_sort_l, range(max_pos+1, len(df)+1)))
            sort_dic.update(not_sort_dic)
            df.Position = df.file.map(sort_dic)
            df.sort_values(by="Position", inplace=True)
            #esborrem la playlist de path_df
            index = path_df[path_df.root == root].index
            path_df.drop(index=index, inplace=True)
            #insertem l'ordenada amb playlist.m3u8
            path_df = pd.concat([path_df, df])
        else: path_df["Smart"] = False
            

    path_df.index = path_df.Position.to_list()
    return path_df


def multiple_str_replace(rep_dic, string, boundary=False):
    rep = dict((re.escape(k), v) for k, v in rep_dic.items())
    if boundary: 
        pattern = re.compile("\\b(" + "|".join(rep.keys()) + ")\\b")
        match_l = pattern.findall(string)
        for match in match_l: 
            string = string.replace(match, rep_dic[match])
    else: 
        pattern = re.compile("|".join(rep.keys()))
        string = pattern.sub(lambda m: rep[re.escape(m.group(0))], string)
    return string

def string_to_seconds(string):
    h_m_s = string.split(":")
    h_m_s = [int(t) for t in h_m_s]
    seconds = h_m_s[-1]
    if len(h_m_s) > 1: seconds += h_m_s[-2] * 60
    if len(h_m_s) > 2: seconds += h_m_s[-3] * 60 * 60
    return seconds

def replace_item_list(lista, old, new):
    return list(map(lambda item: item.replace(old, new), lista))

#--------------------------------SIMILARITY COEFS---------------------------------
def word_list(string):
    string = format_spaces(string)
    string_l = string.split(" ")
    return string_l

def ret_indexes(lista, string):
    return [i for i, x in enumerate(lista) if x == string]

def short_large_str(str1_l, str2_l):
    if len(str1_l) <= len(str2_l): short_str, large_str = str1_l, str2_l
    else: short_str, large_str = str2_l, str1_l
    return short_str, large_str

def number_coincidences(lista1, lista2):
    return len(list(set(lista1).intersection(set(lista2))))

def coincidence_coef(str1_l, str2_l):
    coinc = number_coincidences(str1_l, str2_l)
    
    len_large_str = max([len(str1_l), len(str2_l)])
    return (coinc / len(str1_l)) * (coinc / len(str2_l))

def order_coef(str1_l, str2_l):
    short_str, large_str = short_large_str(str1_l, str2_l)
    counter = 0
    for word, i in zip(short_str, range(len(short_str))):
        if word in large_str:
            i_word = ret_indexes(large_str, word)
            c = 0
            for index in i_word:
                if large_str[index - 1] == short_str[i-1]: c = 1
            counter += c
    return counter / (len(short_str))

def similarity_coef(str1, str2):
    if str1.replace(" ", "") == str2.replace(" ", ""): return 1
    
    str1_l, str2_l = word_list(str1), word_list(str2)
    order_c = order_coef(str1_l, str2_l)
    #apliquem un corrector, doncs el coeficient ens sortirà 0 si cap paraula es consecutiva en ambdos titols
    #i implicarà que ens quedi el similarity_coef=0 i el coincidence_coef sense cap importància
    #així doncs el order_coef en comptes d'anar de (0, 1) anirà de (.8, 1)
    order_c = (order_c / 5) + .8
    coincidence_c = coincidence_coef(str1_l, str2_l)
    return order_c * coincidence_c

#-------------------------------CLEAN------------------------------------
EXTRAS_LIMITS = ["[", "]", "(", ")"]
EXTRAS_LIMITS_REP = {x: "" for x in EXTRAS_LIMITS}
work = ["rmx", "rmix", "remix", "remixed", "re-mixed", "mixed", "re-mix", "r-mix", "mix",
        "edit", "edited", "bootleg", "rework", "mashup", "mash-up", "megamix", "vip", 
        "flip", "reebeef", "dub", "lego's cut", "minimix"]
WORK_REP = {x: "work" for x in work}
symbols = list(r"?!.,:#+-=*_<>@()[]%·'\"/\\")
SYMB_ARTIST_REP = {x: " " for x in symbols}
SYMB_TITLE_REP = SYMB_ARTIST_REP.copy()
SYMB_TITLE_REP.update({";": " "})

a_l = list("áàäâ")
e_l = list("éèëè")
i_l = list("íìïî")
o_l = list("óòöôø")
u_l = list("úùüû")
a_rep = {x: "a" for x in a_l}
e_rep = {x: "e" for x in e_l}
i_rep = {x: "i" for x in i_l}
o_rep = {x: "o" for x in o_l}
u_rep = {x: "u" for x in u_l}
vocals_rep_l = [a_rep, e_rep, i_rep, o_rep, u_rep]
VOCALS_REP = {}
for rep in vocals_rep_l: VOCALS_REP.update(rep)


def format_spaces(string):
    return ' '.join(string.split())

def chars_in_string(string):
    string = string.replace(" ","")
    return len(string)

def remove_symbols(string, artist=False, del_limits=True):
    if artist: rep = SYMB_ARTIST_REP.copy()
    else: rep = SYMB_TITLE_REP.copy()
    if not del_limits: 
        for limit in EXTRAS_LIMITS: rep.pop(limit)  
    string_c = multiple_str_replace(rep, string)
    if chars_in_string(string_c) > 4: return format_spaces(string_c)
    else: return format_spaces(string)

def basic_format_clean(string, spaces=True):
    string_sp = string.lower()
    string_sp = multiple_str_replace(VOCALS_REP, string_sp)
    string_sp = string_sp.replace("&", "and")
    string_sp = format_spaces(string_sp)
    
    if spaces: return string_sp
    else: return string_sp.replace(" ","")

    
def build_artists_c(artists, spaces=True):
    artists = basic_format_clean(artists, spaces=spaces)
    
    artists_ = artists.split(";")
    artists_l = []
    for artist in artists_:
        a = remove_symbols(artist, artist=True)
        a1 = a.replace("the","")
        a1 = format_spaces(a1)
        if len(a1) > 0: a = a1
        if not spaces: a = a.replace(" ","")
        artists_l.append(a)
    
    main_artist = artists_l[0]
    artists_l.remove(main_artist)
    other = ";".join(artists_l)
   
    return main_artist, other

def build_title_c(title, spaces=True):
    title = basic_format_clean(title, spaces=True)
    
    pattern = r"\([^\)]*\)|\[[^\]]*\]"
    extras_l = re.findall(pattern, title)
    
    title_extras_l, title_work_l = [], []
    pattern = re.compile(r"\bwork\b")
    for extra in extras_l:
        title = title.replace(extra, "")
        not_extras = ["ft.", "feat", "original mix", "album version", "original version"]
        if not any([x in extra for x in not_extras]):
            extra = multiple_str_replace(EXTRAS_LIMITS_REP, extra)
            #radio edit no ho considerem com a work
            to_work = True
            if extra in ["radio edit", "radio mix"]: to_work = False
            extra = multiple_str_replace(WORK_REP, extra, boundary=True)
            #si extra du "work".
            if pattern.search(extra): is_work = True
            else: is_work = False
            if is_work & to_work: 
                extra = extra.replace("work", "")
                extra_c = remove_symbols(extra, artist=False)
                if not spaces: extra_c = extra_c.replace(" ","")
                if extra_c == "": extra_c = "unknown"
                title_work_l.append(extra_c)
            else:
                extra_c = remove_symbols(extra, artist=False)
                if not spaces: extra_c = extra_c.replace(" ","")
                title_extras_l.append(extra_c)
    
    title_c = remove_symbols(title, artist=False)
    if not spaces: title_c = title_c.replace(" ","")

    title_extras = ";".join(title_extras_l)
    title_work = ";".join(title_work_l)
    
    return title_c, title_work, title_extras
    
    
def track_clean_dict(artist, title, duration=None):
    main_artist_c, other_artists_c = build_artists_c(artist)
    title_c, title_work_c, title_extras_c = build_title_c(title)
    
    #duration
    if duration == None: duration_sec, duration_str = None, None
    elif type(duration) == str:
        duration_sec = string_to_seconds(duration)
        duration_str = duration
    query = main_artist_c + " " + title_c + " " + title_work_c
    query = format_spaces(query)
                       
    clean_dict = {"main_artist_c": main_artist_c, "other_artists_c": other_artists_c,
                  "title_c": title_c, "title_work_c": title_work_c, "title_extras_c": title_extras_c,
                  "main_artist_cc": main_artist_c.replace(" ", ""), "other_artists_cc": other_artists_c.replace(" ", ""),
                  "title_cc": title_c.replace(" ", ""), "title_work_cc": title_work_c.replace(" ", ""), 
                  "title_extras_cc": title_extras_c.replace(" ", ""),
                  "duration_sec": duration_sec, "query": query}
    return clean_dict

def test_formats(artist, title):
    artist_s = basic_format_clean(artist, spaces=True)
    artist_ = basic_format_clean(artist, spaces=False)
    title_s = basic_format_clean(title, spaces=True)
    title_ = basic_format_clean(title, spaces=False)
    main_artist_c_s, other_artists_c_s = build_artists_c(artist, spaces=True)
    main_artist_c, other_artists_c = build_artists_c(artist, spaces=False)
    title_c_s, title_work_c_s, title_extras_c_s = build_title_c(title, spaces=True)
    title_c, title_work_c, title_extras_c = build_title_c(title, spaces=False)
    clean_dict = {"artist": artist, "title": title,
                  "artist_s": artist_s, "title_": title_s,
                  "artist_": artist_, "title_": title_,
                  "main_artist_c_s": main_artist_c_s, "other_artists_c_s": other_artists_c_s,
                  "main_artist_c": main_artist_c, "other_artists_c": other_artists_c,
                  "title_c_s": title_c_s, "title_work_c_s": title_work_c_s, "title_extras_c_s": title_extras_c_s,
                  "title_c": title_c, "title_work_c": title_work_c, "title_extras_c": title_extras_c}
    return clean_dict



class Linker:
    def __init__(self, tracks_df, finder_df=None, full_lib=True):
        self.tracks_df = tracks_df
        if type(finder_df) != pd.core.frame.DataFrame: self.build_finder(full_lib)
            # thread = threading.Thread(target=self.build_finder)
            # thread.start()
            # thread.join()
        else: self.finder_df = finder_df

    def build_finder(self, full_lib):
        if full_lib: 
            time0 = time.time()
            print("\nGenerant finder_df")
        finder_df = self.tracks_df.copy()
        cols = ['mac_loc', 'mac_pc_loc', 'Artist', 'Name', 'Duration']
        finder_df = finder_df[cols]
        
        finder_df["filename"] = finder_df["mac_pc_loc"].apply(lambda x: x.split(os.sep)[-1].lower())
        finder_df["main_artist_c"], finder_df["other_artists_c"] = zip(*finder_df.Artist.map(build_artists_c))  
        finder_df["title_c"], finder_df["title_work_c"], finder_df["title_extras_c"] = \
                zip(*finder_df.Name.map(build_title_c))
    
        cols = ["main_artist_c", "other_artists_c", "title_c", "title_extras_c", "title_work_c"]
        cc_cols = [col + "c" for col in cols]
        finder_df[cc_cols] = finder_df[cols].applymap(lambda x: x.replace(" ", ""))
        
        finder_df["duration_sec"] = finder_df["Duration"].apply(string_to_seconds)
        # finder_df["query"] = finder_df.artist  + " " + finder_df.title + " " + finder_df.title_extras_c
        
        self.finder_df = finder_df
        if full_lib: 
            finder_df.to_csv("temp/finder_df.csv", index=False)
            print_time("finder_df creat i desat", time0)

   
        
    def artist_coef(self, all_artists, clean_dict):
        main_artist_c, other_artists_c = clean_dict["main_artist_cc"], clean_dict["other_artists_cc"]
        other_artists_c = [a for a in other_artists_c.split(";") if a != ""]
        all_artists_c = [main_artist_c] + other_artists_c
        
        all_artists_l = all_artists.split(";")
        main_artist = all_artists_l[0]
        if len(all_artists_l) != 1: other_artists_l = all_artists_l[1:]
        else: other_artists_l = []
            
        cn = number_coincidences(all_artists_c, all_artists_l)
        if cn == len(all_artists_c) == len(all_artists_l):
            if main_artist_c == main_artist: return 1
            else: return .9
        elif cn == 0: return 0
        else:  
            if main_artist_c == main_artist: return .95
            elif main_artist_c in other_artists_l: return .7 
            else: return .1
    
    
    def build_linked_track(self, linked_track_df, finder_df):
        if not finder_df.empty:
            linked_track_df.loc[0, "mac_pc_loc"] = finder_df.iloc[0]["mac_pc_loc"]
            linked_track_df.loc[0, "mac_loc"] = finder_df.iloc[0]["mac_loc"]
            linked_track_df.loc[0, "level"] = finder_df.iloc[0]["level"]
            linked_track_df.loc[0, "linkable"] = True
        else:
            linked_track_df.loc[0, "level"] = 0
            linked_track_df.loc[0, "linkable"] = False
        
        linked_track_df.level = linked_track_df.level.astype("int")
        
        color = {0: "darkgreen", 1: "sea green", 2: "steel blue",
                 3: "purple4", 4: "purple4", 5: "red"}
        linked_track_df["color"] = linked_track_df.level.map(color)

        #afegim columna per configurar color de title_song al treballar en local
        linked_track_df["title_song_color"] = linked_track_df.level.apply(lambda l: "blue" if l < 4 else "red")
        
        return linked_track_df
        
    #funció per treure dataframe d'info del vinculament amb un audio de la biblioteca
    def build_track_in_library_df(self, filepath, audio=None, all_linkables=False):
        if audio == None: audio = AudioFile(filepath)
        artist, title, duration, creation = audio.artist, audio.title, audio.duration, audio.creation
             
        lista = filepath.split(os.sep)[-2]
        cols = ["Folder", "List", "Artist", "Name", "Duration", "Creation", "pc_loc"]
        linked_track_df = pd.DataFrame(data=[["LOCAL", lista, artist, title, duration, creation, filepath]], 
                                           index=[0], columns=cols)
        
        #generem track_clean_dict
        clean_dict = track_clean_dict(artist, title)
        finder_df = self.finder_df.copy()
        
        if not all_linkables:
            #reductor del dataframe per reduir temps
            cond1 = finder_df.main_artist_cc.str.contains(clean_dict["main_artist_cc"])
            cond2 = finder_df.other_artists_cc.str.contains(clean_dict["main_artist_cc"])
            cond3 = pd.Series(False, index=np.arange(len(finder_df)))#tot false
            for word in clean_dict["title_c"].split(" "):
                cond3 = cond3 | finder_df.title_c.str.contains(word)
            finder_df = finder_df[cond1 | cond2 | cond3]
 
        all_artists_s = (finder_df["main_artist_cc"] + ";" + finder_df["other_artists_cc"]).str.strip(";")
        finder_df["artist_coef"] = all_artists_s.apply(lambda x: self.artist_coef(x, clean_dict))
        
        #incorporem coeficients de similitud de title a finder_df 
        finder_df["title_coef"] = finder_df.title_c.apply(lambda x: similarity_coef(x, clean_dict["title_c"]))
        
        #eliminem els tracks en els que la suma de coeficients de titol i artista es menor que 0.5
        cond = finder_df.artist_coef + finder_df.title_coef < .5
        index = finder_df[cond].index
        finder_df.drop(index=index, inplace=True)
        
        if finder_df.empty:
            if all_linkables: return finder_df
            return self.build_linked_track(linked_track_df, finder_df)
        
        #calculem el work coef com una mitjana entre el producte de la similitud de work i els coef te title i artist
        #d'aquesta manera aportem pes de similitud i, aquest, el ponderem amb els coeficients d'artist i title
        #per una similitud total de work, pero sense coeficient d'artista ni title, el work_coef=0
        def calc_rel_coef(s, feature, value):
            feature_coef = similarity_coef(s[feature], value)
            artist_coef = feature_coef * s.artist_coef
            title_coef = feature_coef * s.title_coef
            coef = (artist_coef + title_coef) / 2
            return coef
        
        title_work_c = clean_dict["title_work_c"]           
        finder_df["work_coef"] = \
        finder_df.apply(lambda s: calc_rel_coef(s, "title_work_c", title_work_c), axis=1)
        
        #amb extras fem igual
        title_extras_c = clean_dict["title_extras_c"]
        finder_df["extras_coef"] = \
        finder_df.apply(lambda s: calc_rel_coef(s, "title_extras_c", title_extras_c), axis=1)
        
        #incorporem duration_dif
        duration = string_to_seconds(duration)
        finder_df["duration_dif"] = finder_df.duration_sec.apply(lambda x: abs(x-duration))
        #coeficient de diferencia de duracions, generat amb sci-kit (funcio polinomial grau 2)
        dif_max, coef_min = 7, .55
        def duration_dif_coef(x):
            if x < 5:
                b0, b1, b2 = 1, (0.94-1)/5, 0
            elif  4 < x <= dif_max:
                b0, b1, b2 = 0.9700000000000002, 0.06249999999999994, -0.017499999999999995
            elif dif_max < x <= 20:
                b0, b1, b2 = 1.331576923076923, -0.13595192307692303, 0.0034711538461538426
            elif x > 20: return 0
            coef = b0 + b1*x + b2*x**2
            return coef

        finder_df["duration_dif_coef"] = finder_df.duration_dif.apply(duration_dif_coef)

        #------------------------------------STANDARD LINK-----------------------------
        #si el title_coef no es més gran q 0.7 no tindrem en compte el extras_coef al level
        #i si es mes gran, unicament si l'artist coef és major q 0.5
        extras_s = finder_df.extras_coef.copy()

        cond1 = finder_df.title_coef < .7
        cond2 = finder_df.artist_coef < .5
        index = finder_df[cond1 | ((~cond1) & cond2)].index
        extras_s.loc[index] = 0

        #sumem els coeficients a level
        finder_df["level"] = finder_df.artist_coef + finder_df.title_coef + finder_df.work_coef + \
                             extras_s + finder_df.duration_dif_coef

        finder_df.sort_values(by=['level', 'title_coef', 'duration_dif'], 
                                 ascending=(False, False, True), inplace=True)

        #un cop ordenats arrodonim els levels (que seguiran amb l'ordre del decimals de level)
        finder_df["level"] = finder_df.level.apply(round)

        if all_linkables: return finder_df
        return self.build_linked_track(linked_track_df, finder_df)   
    
    
    #crea un dataframe amb la informació dels tracks d'un path local comparant amb bilbioteca
    def build_loc_path_synched_df(self, pc_path, path_df=pd.DataFrame(), subfolders=False):
        if path_df.empty: path_df = audio_files_in_folder(pc_path, subfolders)
        if path_df.empty: return path_df #en el cas que el path a afegir no hi hagin audios
        
        local_path_df = pd.DataFrame()
        for row in path_df.itertuples():
            track_in_library_df = self.build_track_in_library_df(row.pc_loc)
            track_in_library_df["pc_mac_loc"] = row.pc_mac_loc
            track_in_library_df["Position"] = row.Position
            track_in_library_df["Length"] = row.Length
            track_in_library_df["Smart"] = row.Smart
            track_in_library_df["Codec"] = row.Codec
            local_path_df = pd.concat([local_path_df, track_in_library_df], axis=0)

        local_path_df.reset_index(drop=True, inplace=True)
        local_path_df["Location"] = local_path_df.pc_loc
        local_path_df["linked"] = local_path_df.level.apply(lambda level: False if level < 4  else True)
        return local_path_df


    # construeix igual el folder a una playlist, pero desde un df (en comptes dun path) per fer refrescos locals
    # tots els arxius que hi hagin al path local no els evaluarà. Treu els que no hi son i afegeix i evalua els nous
    def build_synched_from_list_df(self, list_df):
        path_refresh = os.sep.join(list_df.iloc[0]["Location"].split(os.sep)[:-1])
        df = audio_files_in_folder(path_refresh)
        
        if df.empty: return df, 0, len(list_df) #si no hi ha arxiu es que shan eliminat tots
            
        smart = df.iloc[0]["Smart"]
        list_df.Smart = smart # coloquem el nou smart per si hem incorporat m3a
        list_df.drop(columns=['folder_iid', 'list_iid', 'audio_iid'], inplace=True)

        old_path_df, new_path_df = pd.DataFrame(), pd.DataFrame()
        for row in df.itertuples():
            if row.pc_loc in list_df.pc_loc.to_list():
                track_df = list_df[list_df.pc_loc == row.pc_loc].copy()
                track_df.Position = row.Position
                old_path_df = pd.concat([old_path_df, track_df], axis=0)
            else:
                track_df = df[df.pc_loc == row.pc_loc].copy()
                new_path_df = pd.concat([new_path_df, track_df], axis=0)
        if not new_path_df.empty: 
            new_path_df = self.build_loc_path_synched_df(None, path_df=new_path_df)
            new_path_df = new_path_df.astype({"Smart": bool, "linkable": bool, "linked": bool})
        
        old_path_df = old_path_df.astype({"Smart": bool, "linkable": bool, "linked": bool})

        local_path_df = pd.concat([old_path_df, new_path_df])
        local_path_df.sort_values(by="Position", inplace=True)
        return local_path_df, len(new_path_df), len(list_df) - len(df) + len(new_path_df)



#ALTRES FUNCIONS
def key_from_value(dictionary, value):
    inv_dict = {dictionary[key]: key for key, value in dictionary.items()}
    return inv_dict[value]
    


#funció per extreure imatge, convertida a ImageTk, de metadata
def extract_pic_from_metadata(filepath, size, return_logo=False):
    if return_logo:
        image = Image.open(r"logoblanc.jpg")
        image = image.resize(size)
        return ImageTk.PhotoImage(image)
        
    audio = mutagen.File(filepath)
    hay_art = True
    if filepath.endswith(".mp3"):
        if any(["APIC" in key for key in audio.keys()]):
            pic = audio.tags.getall("APIC")[0].data
        else: hay_art = False
    elif filepath.endswith(".m4a"):
        if "covr" in audio.keys(): pic = audio["covr"][0]
        else: hay_art = False
    if hay_art: image = Image.open(BytesIO(pic))
    else: image = Image.open(r"logoblanc.jpg")
    try:
        image = image.resize(size)
    except:
        image = Image.open(r"logoblanc.jpg")
        image = image.resize(size)
    return ImageTk.PhotoImage(image)

def bpms_iguals_o_multiples(bpm, mybpm, ret_igual=False, ret_multiple=False):
    iguals, multiples = False, False
    bpm, mybpm = int(bpm), int(mybpm)

    if abs(bpm - mybpm) < 3: 
        iguals = True
        multiples = True
    if abs(bpm*2 - mybpm) < 3: multiples = True
    if abs(mybpm*2 - bpm) < 3: multiples = True

    if ret_igual: return iguals
    if ret_multiple: return multiples





#ALTRES FUNCIONS EN DESÚS

def dif_durations(duration1, duration2):
    duration1_s = string_to_seconds(duration1)
    duration2_s = string_to_seconds(duration2)
    return abs(duration1_s - duration2_s)