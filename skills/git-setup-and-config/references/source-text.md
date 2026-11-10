# Source text: Setup and Config

_Cleaned extract from "Pro Git"._

## Setup and Config (pages 484-484)

There are two commands that are used quite a lot, from the first invocations of Git to common every day tweaking and referencing, the `config` and `help` commands.

## Setup and Config > git config (pages 484-484)

Git has a default way of doing hundreds of things. For a lot of these things, you can tell Git to default to doing them a different way, or set your preferences. This involves everything from telling Git what your name is to specific terminal color preferences or what editor you use. There are several files this command will read from and write to so you can set values globally or down to specific repositories.

The `git config` command has been used in nearly every chapter of the book.

In First-Time Git Setup we used it to specify our name, email address and editor preference before we even got started using Git.

In Git Aliases we showed how you could use it to create shorthand commands that expand to long option sequences so you don’t have to type them every time.

In Rebasing we used it to make `--rebase` the default when you run `git pull`.

In Credential Storage we used it to set up a default store for your HTTP passwords.

In Keyword Expansion we showed how to set up smudge and clean filters on content coming in and out of Git.

Finally, basically the entirety of Git Configuration is dedicated to the command.

## Setup and Config > git config core.editor commands (pages 484-486)

Accompanying the configuration instructions in Your Editor, many editors can be set as follows:

### Editor

### Configuration command

Atom


```text
git config --global core.editor "atom --wait"
git config --global core.editor "bbedit -w"
```

BBEdit (macOS, with command line tools)

Emacs


```text
git config --global core.editor emacs
```

Gedit (Linux)


```text
git config --global core.editor "gedit --wait --new-window"
```

Gvim (Windows 64-bit)


```text
git config --global core.editor "'C:\Program
```

`Files\Vim\vim72\gvim.exe' --nofork '%*'"` (Also see note below)

Helix


```text
git config --global core.editor "hx"
```

Kate (Linux)


```text
git config --global core.editor "kate --block"
```

nano


```text
git config --global core.editor "nano -w"
```

Notepad (Windows 64-bit)


```text
git config core.editor notepad
```

Notepad++ (Windows 64-bit)


```text
git config --global core.editor "'C:\Program
Files\Notepad++\notepad++.exe' -multiInst -notabbar -nosession
```

`-noPlugin"` (Also see note below)

Scratch (Linux)


```text
git config --global core.editor "scratch-text-editor"
```

Sublime Text (macOS)


```text
git config --global core.editor "/Applications/Sublime\
Text.app/Contents/SharedSupport/bin/subl --new-window --wait"
```

Sublime Text (Windows 64-bit)


```text
git config --global core.editor "'C:\Program Files\Sublime
```

`Text 3\sublime_text.exe' -w"` (Also see note below)

TextEdit (macOS)


```text
git config --global core.editor "open --wait-apps --new -e"
```

Textmate


```text
git config --global core.editor "mate -w"
```

Textpad (Windows 64-bit)


```text
git config --global core.editor "'C:\Program Files\TextPad
```

`5\TextPad.exe' -m"` (Also see note below)

UltraEdit (Windows 64-bit)


```text
git config --global core.editor Uedit32
```

Vim


```text
git config --global core.editor "vim --nofork"
```

Visual Studio Code


```text
git config --global core.editor "code --wait"
git config --global core.editor "codium --wait"
```

VSCodium (Free/Libre Open

Source Software Binaries of

VSCode)

WordPad


```text
git config --global core.editor "'C:\Program Files\Windows
NT\Accessories\wordpad.exe'"
```

Xi


```text
git config --global core.editor "xi --wait"
```


> **NOTE:** If you have a 32-bit editor on a Windows 64-bit system, the program will be installed in `C:\Program Files (x86)\` rather than `C:\Program Files\` as in the table above.

## Setup and Config > git help (pages 486-486)

The `git help` command is used to show you all the documentation shipped with Git about any command. While we’re giving a rough overview of most of the more popular ones in this appendix, for a full listing of all of the possible options and flags for every command, you can always run `githelp <command>`.

We introduced the `git help` command in Getting Help and showed you how to use it to find more information about the `git shell` in Setting Up the Server.
