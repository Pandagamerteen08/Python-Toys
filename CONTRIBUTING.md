# Contributing to python-toys

Thank you for your interest in contributing to `python-toys`! This repository is designed to be a collection of engaging, self-contained, readable, and fun Python scripts that showcase creative programming, simulations, games, utilities, and audio generators. 

To keep the repository clean, maintainable, and enjoyable for everyone, we have established a set of comprehensive guidelines, structural expectations, and contribution workflows. Please read through this entire document before submitting a pull request.

---

## 1. Core Architectural & Design Philosophy

Every toy added to the repository must adhere to our foundational design principles:

1. **Thematic Directory & Self-Contained Structure:** 
   - All toys must be organized into categorized thematic folders at the repository root (e.g., `audio/`, `games/`, `math/`, `simulations/`, etc.). 
   - Inside the appropriate thematic folder, each individual toy must reside in its own dedicated subfolder named after the toy. 
   - The primary Python script must share the name of its subfolder. For example, if you are contributing a beatbox toy under audio, the path structure must be: `audio/beatbox/beatbox.py`.
   - Contributors are strongly encouraged to work on a dedicated branch for their submission. Within your toy's subfolder, you may optionally include a dedicated `README.md` or a personal license file if you wish to customize authorship attribution.
2. **Standard Library Only:** 
   - No third-party dependencies are allowed under any circumstances. You may **never** require a `pip install`. 
   - Only modules included in the official Python Standard Library may be imported. 
   - If your toy requires generating complex binary outputs like PNG images, WAV audio streams, MIDI files, or animated GIFs, you must implement the lightweight encoder directly inside your script using standard library primitives (such as the `struct`, `wave`, or `zlib` modules).
3. **Python 12+ Compatibility:** 
   - The repository targets modern Python environments. All scripts must be fully compatible with **Python 12 and above**. Take advantage of modern, clean Python features while maintaining backward compatibility with Python 12 runtimes.
4. **Cross-Platform Terminal Compatibility:** 
   - Toys must execute seamlessly across **Windows, macOS, and Linux** within standard terminal environments (PowerShell, Command Prompt, Git Bash, and VS Code terminal).
   - Specifically, ensure proper terminal handling:
     - Call `os.system("")` once on Windows during initialization to properly enable ANSI color code rendering.
     - Wrap Unicode printing by calling `sys.stdout.reconfigure(encoding="utf-8")` inside a `try...except` block to prevent encoding crashes on restricted systems.
     - Handle single-key input gracefully by utilizing `msvcrt` on Windows and `termios`/`tty` on Unix-based systems.
     - If your script utilizes the `multiprocessing` library, always invoke `mp.freeze_support()` and guard your main execution block under `if __name__ == "__main__":`.
5. **Stand-Alone Terminal Scripts, Not GUI Applications:** 
   - Toys must run entirely within the terminal or output directly to files. No heavy GUI frameworks (such as Tkinter, PyQt, or Pygame windows) are permitted. 
   - Furthermore, users should be able to run toys directly on their computer by simply double-clicking the script file if they have Python 12+ installed on their system.
6. **Honesty and Transparency:** 
   - If your code relies on approximations, estimations, heuristic simulations, or synthesized audio algorithms rather than exact physical modeling, explicitly state this limitation in both the script's docstring and any accompanying documentation.

---

## 2. Anatomy of a Great Toy

A high-quality toy is more than just working code; it is a polished, self-documenting piece of software designed to delight users and instruct learners. Every submission should meet the following expectations:

* **Comprehensive Docstring:** Include a clear, informative module-level docstring at the very top of your script. It must feature a concise one-line description of what the toy does, followed by 5 to 8 copy-pasteable example terminal commands demonstrating its various flags, arguments, and presets.
* **Command-Line Interface Support:** 
  - Implement robust command-line argument parsing (preferably using the standard library's `argparse` module).
  - Your script must fully support `--help` to output clean usage instructions.
  - If your toy features multiple presets, themes, modes, or data sets, implement a `--list` flag to display all available options dynamically.
* **Sensible Defaults:** Running your script with zero arguments (`python yourtoy.py` or double-clicking the file) should immediately execute an entertaining, fully functional default demonstration without crashing or demanding immediate input.
* **Reproducibility via Seeding:** Whenever randomness, procedural generation, or stochastic algorithms are used, accept a `--seed` argument so that specific executions, outputs, and simulations are entirely reproducible.
* **Graceful Error Handling:** 
  - Never allow raw Python tracebacks to dump onto the user for common user errors or invalid arguments. 
  - Catch anticipated configuration mistakes, print a clean, user-friendly error message prefixed with `error: ...` to standard error (`sys.stderr`), and exit with a non-zero exit code (`sys.exit(1)`).
  - Utilizing `difflib` to implement "did you mean...?" suggestions for unrecognized arguments or options is strongly encouraged.
* **Code Length & Scope:** 
  - Aim to keep your toy clean, concise, and focused, ideally under approximately 800 lines of code. 
  - If your implementation requires significantly more complexity, it is usually a sign that the logic should be split into two distinct, focused toys.

---

## 3. Step-by-Step Contribution Checklist

Follow this checklist carefully when preparing a new addition to the repository:

1. **Design & Structure:** Create the appropriate thematic directory structure and toy subfolder under the repo root (e.g., `audio/beatbox/beatbox.py`).
2. **Write the Code:** Implement your toy following all style rules, standard library constraints, and CLI interface requirements. Ensure it runs cleanly out-of-the-box on Python 12+.
3. **Configure Test Discovery:** Update the automated test suite configuration so that test discovery routines correctly scan, traverse, and validate scripts located within the new subfolder structure.
4. **Implement Unit & Integration Tests:** 
   - Add comprehensive tests verifying the *correctness* of your code's core logic, rather than merely checking that the script executes without crashing.
   - Excellent test criteria include: verifying published test vectors, testing round-trip data serialization, checking mathematical conservation laws, confirming output stream connectivity, and validating that matching random seeds produce identical output.
5. **Update Documentation (`README.md`):** 
   - Add a new row to the master script table located in the repository's `README.md`, ensuring it is placed under the correct thematic section.
   - Provide a brief usage section explaining how to run your toy and highlighting notable features. Double-check all quoted numbers (such as preset counts, algorithm variations, or configuration limits) against your actual codebase.
6. **Optional Output Artifacts:** If your toy generates static files or exports data, you may optionally include a small, representative sample output file inside an `examples/` directory (keeping individual files under ~1 MB).
7. **Run the Full Test Suite:** Before submitting your work, execute the complete unit test suite locally to ensure absolute stability:
   ```bash
   python -m unittest discover -s tests -v
   ```

---

## 4. Fixing Bugs and Improving Existing Toys

If you notice a bug, performance bottleneck, or missing feature in an existing toy, we welcome improvements:

* **Open an Issue First:** For substantial changes, open an issue or discussion describing the bug or proposed enhancement. Include the exact command run, your operating system, and your Python runtime version.
* **Test-Driven Fixes:** When fixing a bug, first write a unit test that explicitly reproduces and fails under the current codebase, then apply your fix to ensure the test passes cleanly.
* **Focused Pull Requests:** Keep pull requests tightly scoped. Address one bug fix or feature addition per pull request to streamline code review.

---

## 5. Code Style and Best Practices

To maintain a codebase that is accessible to programmers of all skill levels, adhere to these coding standards:

* **Plain, Readable Python:** Write straightforward, readable Python code. Elegant, short, and explicit functions are heavily preferred over overly clever, dense, or heavily abstracted metaprogramming tricks.
* **Comment for Intent:** Write comments that explain **why** a complex decision or algorithmic shortcut was made, rather than restating **what** the code is literally doing line-by-line.
* **Zero External Dependencies & Network Isolation:** Scripts must never attempt network requests, socket connections, web scraping, or file writes outside of user-specified output arguments.
* **Secure Randomness:** Whenever your toy involves security-sensitive operations, token generation, or cryptographic identifiers, you must use Python's built-in `secrets` module or `os.urandom()` rather than the standard `random` module.

---

## 6. Pull Request Submission Guidelines

When you are ready to submit your contribution for review:

* **Detailed Description:** Provide a clear, detailed summary explaining what your toy or change does. Paste a representative sample command alongside its actual terminal output in the pull request description.
* **Environment Details:** Specify which operating systems (Windows, macOS, Linux) and exact Python versions you used to test your submission.
* **Licensing Agreement:** By submitting a pull request to `python-toys`, you agree to license your contributed work under the repository's standard MIT License.

---

## 7. Community Guidelines & Code of Conduct

**Be kind.** Maintain a welcoming, friendly, and constructive tone in all issues, pull request reviews, and community discussions. Always assume positive intent, and remember that the primary mission of the `python-toys` repository is to celebrate creativity, learning, and fun through programming.
