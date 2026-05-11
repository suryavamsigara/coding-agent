import sys

def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("--version", "-version", "-v", "--v", "-V", "--V"):
        from importlib.metadata import version
        print(f"Tenet {version('tenet')}")
        return
    
    from tenet.ui.cli import start_tenet
    start_tenet()

if __name__ == "__main__":

    main() 