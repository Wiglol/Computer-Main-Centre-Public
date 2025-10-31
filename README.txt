📘 Computer Main Centre (CMC)
Local command console for file automation and Git integration.

🚀 How to Run

Double-click Start_CMC.vbs to launch the console.

Type help to explore commands.

For instant path search, build your first index:

/qbuild


(this scans your drives and creates a local paths.db)

⚠️ If You See
❌ Error: cannot DELETE from contentless fts5 table: paths_fts


It means an old or corrupted paths.db file was detected.
To fix:

Close CMC

Delete paths.db from the CMC folder

Restart CMC and run /qbuild again

🧭 Requirements

Python 3.10 + (installed & added to PATH)

Git for Windows (for GitHub integration)

💡 Tip

You can use /gitsetup, /gitupdate, /gitstatus, and /gitdoctor right inside CMC — no external terminal needed.

Last Updated 01/11/2025