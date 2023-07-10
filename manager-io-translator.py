# author Oleksander Kechedzhy
# version 1.0
#
import json
import os
import re
import sys
import time
import typing as tp
from random import random

import deep_translator as dt
from typing_extensions import Self

from tasks_pool import TaskPoolCoroutine, TasksPool, TaskPoolCoroutineList

TEST_MODE: bool = False
# True - for testing purposes. It copies source language
# strings without translation to the target JSON file.
# False - normal translation through deep_translator

STR_LIMIT: int = 0          # limits the number of the strings to translate
MAX_THERADS: int = 6        # Max threads in pool
STR_PER_BATCH: int = 20     # number of strings per batch
MAX_ATTEMPTS: int = 3       # run translation MAX_ATTEMPTS times until all strings will be translated.

ENCODING = "utf-8"
BYTES_PER_BATCH = 4999
JSON_INDENT = "\t"
LINE_CLEAR = '\033[K'
EOL = ".§ "             # "\n" .<br> *
EOL2 = r"\.\s*§\s*"
test_mode: bool = TEST_MODE


def do_translation(text: str, csr_lang: str, translator: tp.Any, count: int) -> str:
    try:
        result: str = translator.translate(text)
    except Exception as exc:
        print(f'do_translation() exception: {exc!r}')
        result = ""
    # }
    return result
# }


class TaskPacketTranslation(TaskPoolCoroutine):
    def __init__(self, index: int, csr_lang: str, tgt_lang: str, proxies: dict[str, str] | None = None):
        super().__init__(index)
        self.text_batch: list[str] = []
        self.csr_lang: str = csr_lang
        self.tgt_lang: str = tgt_lang
        self.text_keys: list[str] = []
        self.count: int = 0
        self.text: str = ""
        self.count_done: int = 0
        self.b_number: int = 0
        self.targer: tp.Any = None
        global test_mode
        if not test_mode:
            if isinstance(proxies, str):
                proxies = {'https': proxies}
            # }
            self.translator = dt.GoogleTranslator(source=csr_lang, target=tgt_lang, proxies=proxies)
        # }
    # }

    def doTask(self, text_batch: list[str], targer: tp.Any, text_keys: list[str], count: int, b_number: int) -> Self:
        self.text_batch = text_batch
        self.targer: tp.Any = targer
        self.text_keys = text_keys
        self.count = count
        self.count_done = 0
        self.b_number = b_number
        global test_mode

        try:
            if test_mode:
                time.sleep(0.5 + random() * 2)
                self.text = EOL.join(text_batch[:count])  # do_translation()
                self.result = re.split(EOL2, self.text)
            else:
                self.text = do_translation(EOL.join(text_batch[:count]), self.csr_lang, self.translator, count)
                self.result = re.split(EOL2, self.text)
                # check for upper case?
                for i, (text, rs) in enumerate(zip(self.result, text_batch[:count])):
                    if not rs[0].isupper():
                        if text.lstrip()[0].isupper():  # check if translation is titled
                            self.result[i] = rs[0].upper() + rs[1:]
                        # }
                    # }
                # }
            # }
            # post check 
            self.count_done = len(self.result)
        # }
        except Exception as exc:
            print(f'do_translation() exception: {exc!r}')
            self.result = None
        # }
        return self
    # }

    def doSaveResult(self) -> tuple[int, int]:
        global test_mode
        d_count: int = 0
        if self.result is not None and self.count_done > 0:  # self.count_done==self.count:
            for rs, origin, key in zip(self.result, self.text_batch, self.text_keys):  # , self.text_batch
                if test_mode:
                    if origin != rs:
                        print(f"TEST ERROR: Save {key}: {origin} ---> {rs}")
                        continue
                    # }
                # }
                self.targer[key] = rs  # save result
                d_count += 1
            # }
        # }
        if d_count != self.count:
            print(f"* Data inconsistency on batch #{self.b_number}-{self.index}: sent: {self.count} strings, in result: {self.count_done}! {d_count} saved.")
        # }
        return d_count, self.count - d_count
    # }
# } TaskPacketTranslation


class TaskPacketTranslationList(TaskPoolCoroutineList):
    def __init__(self, max_size: int, csr_lang: str, tgt_lang: str):
        super().__init__(max_size)
        self.csr_lang: str = csr_lang
        self.tgt_lang: str = tgt_lang

    # }

    def createNew(self, index: int) -> TaskPacketTranslation:
        return TaskPacketTranslation(index, self.csr_lang, self.tgt_lang)
    # }

# } TaskPoolCoroutineList


class TranslateTasksPool(TasksPool):
    def __init__(self, poll_size: int, coroutine_list: TaskPoolCoroutineList) -> None:
        super().__init__(poll_size, coroutine_list)

    # }

    def save_progress(self, done: int, fault: int = 0) -> None:
        if done + fault > 0:
            super().save_progress(done, fault)
            print(LINE_CLEAR + f"Translated total {self.totalDone} strings (fault {self.totalFault}).", end="\r", flush=True)
        # }
    # }

# }TranslateTasksPool


def PrintCommandLineUsage():
    print(f"Usage: python -m translate_json [-from | -fromfile | -to | -tofile | -save-branch | -save-source] <arguments>...")
    print("-from <language code>\t-- source language code of two symbol e.g.(sl | de).")
    print("-fromfile <file name>\t-- source file name with path (default Translations.json).")
    print("-to <language code>\t-- target language.")
    print("-save-strings \t\t-- if the source Translations.json save translated strings to Strings_<xx>.json.")
    print("-save-source\t\t-- if the source Translations.json save translated strings into the source json file as well.")
    print("-test\t\t-- copy strings from source to target language JSON without translation.")
    print("\t\t\t   * If target file exists it will be used to load already translated strings (instead of source).")
# }


def CheckCLParameter(param_name: str, argv: list[str], lev_argv: int) -> str | None:
    param = None
    if param_name in argv:
        index = argv.index(param_name) + 1
        if index < lev_argv:
            param = argv[index]
        # }
    # }
    return param
# }


#
def main():
    argv: list[str] = sys.argv[1:]
    if len(argv) == 0:
        PrintCommandLineUsage()
        return
    # }
    # print(sys.argv[1:])

    json_from_file_path: tp.Any
    strings_json_to_file: tp.Any = None
    json_to_file: tp.Any = None
    csr_lang: str | None
    tgt_lang: str | None
    json_from_file_name: str
    translation_source: bool = False
    save_source: bool = False
    strings_source: bool = False
    to_strings_file: bool = False
    tg_tr: tp.Any
    global test_mode
    len_argv: int = len(argv)

    strings_per_packet: int = max(20, STR_PER_BATCH)  # Translate by strings_per_packet in one request

    csr_lang = CheckCLParameter("-from", argv, len_argv)
    if csr_lang is None:
        print("Please provide source language code (-sl <code>) or use 'auto' to find any language with 100 persantage translation.\n\r")
        PrintCommandLineUsage()
        return
    # }

    tgt_lang = CheckCLParameter("-to", argv, len_argv)
    if tgt_lang is None:
        print("Please provide target language code (-tl <code>)!\n\r")
        PrintCommandLineUsage()
        return
    # }

    json_from_file_path = CheckCLParameter("-fromfile", argv, len_argv)
    if json_from_file_path is None:
        json_from_file_name = 'Translations.json'
        json_from_file_location = ""
        translation_source = True
    else:
        json_from_file_name = os.path.basename(json_from_file_path)
        json_from_file_location = os.path.dirname(json_from_file_path)
    # }

    if json_from_file_name == "Strings.json":
        strings_source = True
        to_strings_file = True
        json_to_file = os.path.join(json_from_file_location, f'Strings_{tgt_lang}.json')
        strings_json_to_file = json_to_file
    # }
    
    if "-save-strings" in argv and not strings_source:
        strings_json_to_file = os.path.join(json_from_file_location, f'Strings_{tgt_lang}.json')
        to_strings_file = True
    # }

    if json_from_file_name == "Translations.json":
        translation_source = True
        json_to_file = os.path.join(json_from_file_location, f'Translations_{tgt_lang}.json')
    # }

    if not os.path.isfile(json_from_file_path):
        print(f"File {json_from_file_name} was not find in the path {json_from_file_location}!\n\r")
        return
    # }

    if not test_mode and "-test" in argv and translation_source:
        test_mode = True
    # }

    if "-save-source" in argv and translation_source:
        save_source = True
    # }

    translations_tg = None
    with open(file=json_from_file_path, encoding=ENCODING) as f:
        translations = json.load(f)

    if os.path.isfile(json_to_file):
        with open(file=json_to_file, encoding=ENCODING) as f:
            translations_tg = json.load(f)
    # }

    print(f"Source json file was loaded at {time.strftime('%X')}.")

    if translation_source and save_source:
        tg_tr = translations[tgt_lang]["Strings"]   # to save the same file Translations.json [and Translations_xx.json]
    else:
        if translations_tg is None:
            tg_tr = dict({})    # new empty json
        else:
            if translation_source:
                tg_tr = translations_tg[tgt_lang]["Strings"]    # save the same format as in Translations.json
            else:   # if strings_source:
                tg_tr = translations_tg
            # }
        # }
    # }

    tg_len = len(tg_tr)
    if translation_source:
        if not translations.get(csr_lang):
            print(f"Source language {csr_lang} is absent in {json_from_file_name}!\n\r")
            return
        # }
        sc_tr = translations[csr_lang]["Strings"]
        sc_len = len(sc_tr)
        sc_percentage = int(translations[csr_lang]["Percentage"])
        strings_estimated = int(sc_len * 100 / sc_percentage)
    else:
        sc_tr = translations
        sc_len = len(sc_tr)
        strings_estimated = sc_len
        sc_percentage = 100
    # }

    print(f"Total {sc_len} strings in source language ({tg_len} in target language).")
    if sc_percentage < 100:
        print(f"The estimated total count of the strings should be {strings_estimated}.")
    # }

    translation_packets = TaskPacketTranslationList(MAX_THERADS, csr_lang, tgt_lang)
    treads_poll = TranslateTasksPool(MAX_THERADS, translation_packets)

    text_batch: list[str] = ["" for _ in range(strings_per_packet)]
    text_keys: list[str] = ["" for _ in range(strings_per_packet)]
    batch_len: int
    total_batch_len: int
    added: int
    copies: int = 0
    clone: int = 0
    i: int
    j: int
    attempts: int = 0
    total_done: int = 0
    max_strings: int = STR_LIMIT or sc_len
    while total_done+clone+tg_len < sc_len and attempts < MAX_ATTEMPTS and total_done < max_strings:
        added = 0
        copies = 0
        total_batch_len, t, b_number = 0, 0, 1
        treads_poll.reset_progress()

        for key_sc, val_sc in sc_tr.items():
            if translation_source:
                if translations[tgt_lang]["Strings"].get(key_sc) and not tg_tr.get(key_sc):     # copy existing translation
                    tg_tr[key_sc] = translations[tgt_lang]["Strings"][key_sc]
                    clone += 1
                    continue
                # }
            # }
            i, j = 0, 0
            if not tg_tr.get(key_sc):
                i = 1
            elif tg_tr[key_sc] == val_sc:
                j = 1
            # }        
            if (i + j) > 0:  # need to translate new string from the source language
                batch_len = len(val_sc.encode(ENCODING))
                if total_batch_len + batch_len >= BYTES_PER_BATCH or t == strings_per_packet:
                    treads_poll.submitTaskInPool(text_batch[:t].copy(), tg_tr, text_keys[:t].copy(), t, b_number)
                    b_number += 1
                    total_batch_len = 0
                    t = 0
                # }
                total_batch_len += batch_len
                text_batch[t] = val_sc
                text_keys[t] = key_sc
                t += 1
                added += i
                copies += j
                if 0 < STR_LIMIT <= (added + copies):
                    max_strings = -1
                    break
                # }
            # }
        # }
        attempts += 1
        if added + copies > 0:
            if t > 0:
                treads_poll.submitTaskInPool(text_batch[:t].copy(), tg_tr, text_keys[:t].copy(), t, b_number)
            # }
            total_done += treads_poll.waitForAllTasks()
            #print(f"Added new {added} strings from the language \"{csr_lang}\". {added + copies} strings passed to google translater.")
        # }
    # }
    
    print(LINE_CLEAR)

    if total_done > 0:
        # SORTING by key
        tg_tr = dict(sorted(tg_tr.items()))
        tg_new_len: int = len(tg_tr)
        tg_percentage = int(100 * (tg_len - copies + total_done + clone) / strings_estimated)

        print(f"{total_done} strings were successfully translated ({tg_percentage}% of total text) in {attempts} attempts.")
        print(f"{tg_new_len} strings in the result JSON file.")

        if translation_source:
            translations[tgt_lang]["Strings"] = tg_tr
            translations[tgt_lang]["Percentage"] = tg_percentage
            if save_source and not test_mode:
                with open(file=json_from_file_name, mode="w", encoding=ENCODING) as outfile:
                    json.dump(obj=translations, fp=outfile, skipkeys=False, ensure_ascii=False, indent=JSON_INDENT)
                print(f"Translated strings saved to origin file {json_from_file_name}.")
            # }
            if translations_tg is None:
                translations_tg = dict([(tgt_lang,None)])
                translations_tg[tgt_lang] = translations[tgt_lang]
            else:
                translations_tg[tgt_lang]["Strings"] = tg_tr
                translations_tg[tgt_lang]["Percentage"] = tg_percentage
            # }
            with open(file=json_to_file, mode="w", encoding=ENCODING) as outfile:
                json.dump(obj=translations_tg, fp=outfile, skipkeys=False, ensure_ascii=False, indent=JSON_INDENT)
            print(f"Target language strings saved to {os.path.basename(json_to_file)}.")
        # }

        if to_strings_file and strings_json_to_file is not None:
            with open(file=strings_json_to_file, mode="w", encoding=ENCODING) as outfile:
                json.dump(obj=tg_tr, fp=outfile, skipkeys=False, ensure_ascii=False, indent=JSON_INDENT)
            print(f"Target language strings saved to {os.path.basename(strings_json_to_file)}.")
        # }
        print(f"All done at {time.strftime('%X')}. Goodbye!")
    else:
        print(f"Nothing to do!")
    # }
# }


#
if __name__ == '__main__':
    main()
# }
