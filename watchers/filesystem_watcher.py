from watchdog.observers.polling import PollingObserver as Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
import shutil, logging, time
logging.basicConfig(level=logging.INFO)

class DropFolderHandler(FileSystemEventHandler):
    def __init__(self, vault_path):
        self.needs_action = Path(vault_path) / 'Needs_Action'

    def on_created(self, event):
        if event.is_directory: return
        source = Path(event.src_path)
        dest = self.needs_action / f'FILE_{source.name}'
        shutil.copyfile(source, dest)
        (dest.with_suffix('.md')).write_text(
            f'---\ntype: file_drop\noriginal_name: {source.name}\n---\nNew file dropped.'
        )
        logging.info(f'New file detected: {source.name}')

if __name__ == '__main__':
    import sys
    vault = sys.argv[1] if len(sys.argv) > 1 else '~/AI_Employee_Vault'
    handler = DropFolderHandler(vault)
    observer = Observer()
    observer.schedule(handler, str(Path(vault) / 'Inbox'), recursive=False)
    observer.start()
    logging.info(f'Watching {vault}/Inbox for new files...')
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
