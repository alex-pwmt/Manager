# manager-io-translator.py

The manager-io-translator.py is a localization tool for Manager.io accounting software. It translates from Translations.json and/or Strings.json files using deep_translator and saves the translated strings to an appropriate JSON file.

Inputs: - The manager-io-translator takes command-line arguments as inputs, including a source language code, a target language code, and file paths for the source and target JSON files. - Other inputs include constants and variables defined within the app, such as the maximum number of threads, batch size, and maximum number of translation attempts.

Flow:

- The manager-io-translator parses the command-line arguments at first and sets up variables and constants for the translation process.
- Loads the source JSON file and checks if a target JSON file exists for loading previously translated strings.
- Iterates through the source strings and checks if they need to be translated based on if they exist in the target JSON file or not.
- If a string needs to be translated, it is added to a batch of strings to be sent to the translation API.
- Submits the batch of strings to the translation API using multiple threads and waits for the translations to complete.
- When all translations are completed, the app saves the translated strings to the target JSON file and/or a separate strings JSON file if it was specified in the command-line arguments.

Outputs:

- The main outputs of the manager-io-translator are the translated strings saved to the target JSON file and/or a separate JSON file if specified in the command-line arguments.
- The app includes options to copy strings from the source to the target JSON file without translation for testing purposes.

## CLA

Usage: python -m translate_json [-from | -fromfile | -to | -tofile | -save-branch | -save-source] arguments ...

    -from language code -- source language code of two symbol e.g.(sl | de).
    -fromfile file name -- source file name with path (default Translations.json).
    -to language code -- target language.
    -save-strings -- if the source Translations.json save translated strings to Strings_xx.json.
    -save-source -- if the source Translations.json save translated strings into the source JSON file as well.
    -test -- copy strings from source to target language JSON without translation.
    * If the target file exists it will be used to load already translated strings (instead of source).

### Examples

manager-io-translator.py -from sl -to pl -fromfile Translations.json -save-strings -save-source

    translate strings from Translations.json from "sl" to "pl" language, save results to Translations.json for "pl" language, Translations_pl.json, and Strings_pl.json.
