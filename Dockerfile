# Use the Fedora 32 base image
FROM fedora:32 as base

# Install Python 3.8 and other required packages
RUN dnf -y install python38 python3-pip gcc make wget

FROM base as qt5Generator

# Install PyQt5 development tools
RUN dnf -y install python3-qt5-devel

# Install PyInstaller and PyQt5 and other required packages
RUN python3.8 -m pip install PyQt5

WORKDIR /app

COPY . .

RUN make ui
RUN make res

FROM base as pyinstaller

# Install PyInstaller and other required packages
RUN python3.8 -m pip install pyinstaller

WORKDIR /app
COPY --from=qt5Generator /app ./

RUN python3.8 setup.py build
RUN python3.8 setup.py install

# Compile the script into a static executable
RUN pyinstaller --onefile --clean --noconfirm bin/qubes-qube-manager

CMD cp /app/dist/* /fancy