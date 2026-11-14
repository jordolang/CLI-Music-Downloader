import curses
import os
import subprocess
import sys
import asyncio
from typing import Optional, Callable

# Add scripts directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(script_dir, "scripts"))

# — Pre-flight check for required libraries
try:
    import curses
except ImportError:
    print("The 'curses' library is not available on your system.")
    print("This TUI requires a POSIX-like environment (Linux, macOS).")
    sys.exit(1)

# Import UI functions from CLI tools
from cli_music_downloader.download_music import download_music_ui, get_download_help

try:
    from scripts.lyrics_metadata import get_lyrics_ui, get_lyrics_help
    from scripts.metadata_manager import get_metadata_help
    from scripts.run_tests import run_tests_ui, get_tests_help
except ImportError as e:
    print(f"Warning: Could not import some UI functions: {e}")
    print("Some features may not be available.")

# Import batch metadata help
try:
    from batch_metadata import get_batch_metadata_help
except ImportError:
    def get_batch_metadata_help():
        return "Batch metadata tool help not available."

class CursesUI:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        curses.curs_set(0)
        self.stdscr.clear()
        self.stdscr.refresh()

        self.menu_items = [
            ("Download Music", self.run_download_music),
            ("Get Lyrics", self.run_get_lyrics),
            ("Batch Metadata Tool", self.show_batch_metadata_help),
            ("Run Tests", self.run_tests),
            ("Install", self.run_install),
            ("Uninstall", self.run_uninstall),
            ("Help", self.show_help),
            ("Exit", None),
        ]

    def run(self):
        current_row = 0

        while True:
            self.stdscr.clear()
            h, w = self.stdscr.getmaxyx()

            for idx, item in enumerate(self.menu_items):
                x = w // 2 - len(item[0]) // 2
                y = h // 2 - len(self.menu_items) // 2 + idx
                if idx == current_row:
                    self.stdscr.attron(curses.A_REVERSE)
                    self.stdscr.addstr(y, x, item[0])
                    self.stdscr.attroff(curses.A_REVERSE)
                else:
                    self.stdscr.addstr(y, x, item[0])

            self.stdscr.refresh()

            key = self.stdscr.getch()

            if key == curses.KEY_UP and current_row > 0:
                current_row -= 1
            elif key == curses.KEY_DOWN and current_row < len(self.menu_items) - 1:
                current_row += 1
            elif key == curses.KEY_ENTER or key in [10, 13]:
                selected_action = self.menu_items[current_row][1]
                if selected_action:
                    selected_action()
                else:  # Exit
                    break

    def get_user_input(self, prompt: str) -> str:
        self.stdscr.clear()
        self.stdscr.addstr(0, 0, prompt)
        self.stdscr.refresh()
        curses.echo()
        input_str = self.stdscr.getstr(1, 0).decode("utf-8")
        curses.noecho()
        return input_str

    def display_output(self, title: str, output: str):
        self.stdscr.clear()
        self.stdscr.addstr(0, 0, title, curses.A_BOLD)
        self.stdscr.addstr(2, 0, output)
        self.stdscr.addstr(self.stdscr.getmaxyx()[0] - 1, 0, "Press any key to continue...")
        self.stdscr.getch()

    def run_download_music(self):
        search_term = self.get_user_input("Enter search term (e.g., artist - title):")
        if search_term:
            success, message = download_music_ui(search_term)
            self.display_output("Download Music", message)

    def run_get_lyrics(self):
        artist = self.get_user_input("Enter artist:")
        title = self.get_user_input("Enter title:")
        if artist and title:
            success, lyrics = get_lyrics_ui(artist, title)
            self.display_output(f"Lyrics for {artist} - {title}", lyrics)

    def show_batch_metadata_help(self):
        help_text = get_batch_metadata_help()
        self.display_output("Batch Metadata Tool Help", help_text)

    def run_tests(self):
        success, message = run_tests_ui()
        self.display_output("Test Results", message)

    def run_install(self):
        # We need to capture the output of the shell script
        import subprocess
        process = subprocess.Popen(["bash", os.path.join(script_dir, "scripts", "install.sh")], 
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()
        output = stdout + stderr
        self.display_output("Installation", output)

    def run_uninstall(self):
        import subprocess
        process = subprocess.Popen(["bash", os.path.join(script_dir, "scripts", "uninstall.sh")], 
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()
        output = stdout + stderr
        self.display_output("Uninstallation", output)

    def show_help(self):
        help_text = f"""{get_download_help()}

{get_lyrics_help()}

{get_metadata_help()}

{get_batch_metadata_help()}

{get_tests_help()}

{get_install_help()}

{get_uninstall_help()}
"""
        self.display_output("Help", help_text)

def browse_files(screen):
    """Browses files in a simple file explorer."""
    
    current_path = os.getcwd()
    selected_file = None

    while True:
        screen.clear()
        
        # -- Display current path
        screen.addstr(0, 0, f"Current Directory: {current_path}")
        
        # -- Get and display directory contents
        try:
            items = os.listdir(current_path)
            # -- Separate directories and files
            dirs = sorted([d for d in items if os.path.isdir(os.path.join(current_path, d))])
            files = sorted([f for f in items if os.path.isfile(os.path.join(current_path, f))])
            
            # -- Combine for display
            display_items = ["[..] (Go up)"] + dirs + files
            
        except OSError as e:
            screen.addstr(2, 0, f"Error: {e}")
            screen.addstr(4, 0, "Press any key to return...")
            screen.getch()
            return None

        # -- Display items in a scrollable list
        max_y, max_x = screen.getmaxyx()
        
        pad_height = len(display_items) + 2
        pad_width = max_x - 4
        
        pad = curses.newpad(pad_height, pad_width)
        pad.scrollok(True)
        pad.idlok(True)

        for i, item in enumerate(display_items):
            pad.addstr(i, 0, item)

        pad_pos = 0
        current_row = 0

        while True:
            pad.refresh(pad_pos, 0, 2, 2, max_y - 2, max_x - 2)
            
            # -- Highlight current selection
            pad.chgat(current_row, 0, -1, curses.A_REVERSE)
            
            key = screen.getch()
            
            # -- Remove highlight before next action
            pad.chgat(current_row, 0, -1, curses.A_NORMAL)
            
            if key == curses.KEY_UP and current_row > 0:
                current_row -= 1
            elif key == curses.KEY_DOWN and current_row < len(display_items) - 1:
                current_row += 1
            elif key == curses.KEY_ENTER or key in [10, 13]:
                selected_item_name = display_items[current_row]
                
                if selected_item_name == "[..] (Go up)":
                    # -- Go to parent directory
                    current_path = os.path.dirname(current_path)
                    break
                
                full_path = os.path.join(current_path, selected_item_name)
                
                if os.path.isdir(full_path):
                    # -- Navigate into subdirectory
                    current_path = full_path
                    break
                else:
                    # -- File selected, return it
                    return full_path
            
            elif key == ord("q"):
                # -- Quit file browser
                return None
        
        # -- Refresh outer loop if directory changes
        if key == curses.KEY_ENTER or key in [10, 13]:
            continue

def get_file_path(screen, prompt):
    """Allow user to either type a path or browse for a file."""
    screen.clear()
    screen.addstr(0, 0, prompt)
    screen.addstr(2, 0, "Choose an option:")
    screen.addstr(3, 0, "1. Type file path manually")
    screen.addstr(4, 0, "2. Browse for file")
    screen.addstr(6, 0, "Enter your choice (1 or 2): ")
    screen.refresh()
    
    curses.echo()
    choice = screen.getstr(6, 28).decode("utf-8").strip()
    curses.noecho()
    
    if choice == "1":
        return get_user_input(screen, "Enter the full file path: ")
    elif choice == "2":
        file_path = browse_files(screen)
        if file_path:
            return file_path
        else:
            screen.clear()
            screen.addstr(0, 0, "No file selected. Press any key to continue...")
            screen.getch()
            return None
    else:
        screen.clear()
        screen.addstr(0, 0, "Invalid choice. Press any key to continue...")
        screen.getch()
        return None

def get_user_input(screen, prompt):
    """Gets user input in a separate window."""
    screen.clear()
    screen.addstr(0, 0, prompt)
    screen.refresh()
    curses.echo()
    input_str = screen.getstr(1, 0).decode("utf-8")
    curses.noecho()
    return input_str

def display_output(screen, output):
    """Displays multi-line output in a scrollable pad."""
    screen.clear()
    
    pad_height = 1000 
    pad_width = curses.COLS - 4
    
    pad = curses.newpad(pad_height, pad_width)
    pad.scrollok(True)
    pad.idlok(True)

    for i, line in enumerate(output.splitlines()):
        pad.addstr(i, 0, line)

    pad_pos = 0
    while True:
        max_y, max_x = screen.getmaxyx()
        pad.refresh(pad_pos, 0, 1, 1, max_y - 2, max_x - 2)
        
        key = screen.getch()
        if key == curses.KEY_UP and pad_pos > 0:
            pad_pos -= 1
        elif key == curses.KEY_DOWN and pad_pos < pad_height - max_y + 2:
            pad_pos += 1
        elif key == ord("q"):
            break

def main(stdscr):
    ui = CursesUI(stdscr)
    ui.run()


if __name__ == "__main__":
    curses.wrapper(main)
