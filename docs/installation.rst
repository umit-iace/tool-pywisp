============
Installation
============

General Options
---------------

At the command line with `uv` installed::

    $ git clone https://github.com/umit-iace/tool-pywisp
    $ cd tool-pywisp
    $ uv venv
    $ uv sync


For Windows
-----------

Using of `WSL` (Windows-Subsystem for Linux) at the command line::


    $ wsl -- install archlinux

After installation is done, you can switch in the `WSL` enviroment with::

    $ wsl

and install the following packages::

    $ pacman -Syu
    $ pacman -S python3 uv eigen cmake arm-none-eabi-gcc git make gcc libgl qt5-base

Finally::

    $ git clone https://github.com/umit-iace/tool-pywisp
    $ cd tool-pywisp
    $ uv venv
    $ uv sync

