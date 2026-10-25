# python-toys

A sprawling, standalone collection of interactive single-file Python programs designed for creation, simulation, experimentation, and play. Covering everything from procedural world generation and retro arcade-style roguelikes to audio synthesis, mathematical fractals, ciphers, and algorithmic physics simulations, **python-toys** requires **no external dependencies, no third-party libraries, and no `pip install` whatsoever**. 

Every single file in this repository is completely self-contained. They run straight out-of-the-box using the standard library, compatible with standard terminal environments (PowerShell, Command Prompt, Git Bash, macOS, and Linux terminals) as well as directly inside VS Code.

![fractal gallery](examples/fractal-gallery.jpg)

---

## Repository Architecture & Directory Tree

To maintain pristine organization and scalability, all scripts are neatly categorized into thematic domain folders. Each toy resides in its own dedicated subfolder, ensuring complete independence:

```text
python-toys/
├── audio/
│   ├── beatbox/
│   │   └── beatbox.py
│   └── synth/
│       └── synth.py
├── dungeon/
│   └── dungeon.py
├── math/
│   ├── fractals/
│   │   └── fractals.py
│   ├── lsystem/
│   │   └── lsystem.py
│   └── sortviz/
│       └── sortviz.py
├── maze/
│   └── maze.py
├── namegen/
│   └── namegen.py
├── simulations/
│   ├── lifegame.py
│   └── simlab.py
├── story/
│   └── storyspark.py
├── utilities/
│   ├── cipher.py
│   └── randomizer.py
├── worldgen/
│   └── worldgen.py
├── tests/
│   ├── test_toys.py
│   └── test_more.py
└── examples/
    ├── fractal-gallery.jpg
    ├── world.png
    ├── plant.png
    └── dragon.png

```

---

## Complete Toy Inventory & Detailed Breakdown

Below is the master catalog of all available toys categorized by their operational domain, complete with technical descriptions and core capabilities:

### 1. Audio & Sound Generation

* **[`audio/beatbox/beatbox.py`](https://www.google.com/search?q=audio/beatbox/beatbox.py)**
* *What it does:* Translates plain-English text prompts into professional stereo beatbox tracks exported as `.wav` files, with optional multi-channel MIDI drum exports.
* *Key Features:* Features 33 distinct synthesized mouth-sound voices (kicks, snares, hi-hats, scratches, bass hums, lip rolls, throat bass), 25 style presets (trap, dnb, garage, waltz, dubstep), automatic song arrangement structures (intro, groove, breakdown, drop), swing timing adjustment, and custom sample loading (`--samples`).


* **[`audio/synth/synth.py`](https://www.google.com/search?q=audio/synth/synth.py)**
* *What it does:* Composes complete musical arrangements (chord progressions, basslines, melodic leads, and percussion) directly from natural language prompts.
* *Key Features:* Generates fully mastered WAV audio streams alongside complete MIDI file exports. Handles tempo, emotional keys, instrumentation weighting, and dynamic envelope shaping entirely through standard library binary buffer writing.



### 2. Procedural Generation & Worldbuilding

* **[`worldgen/worldgen.py`](https://www.google.com/search?q=worldgen/worldgen.py)**
* *What it does:* Constructs sprawling fantasy world maps from scratch using multi-octave Perplex/Simplex noise elevation modeling, hydraulic erosion simulation, biome temperature/moisture mapping, river carving algorithms, and procedural settlement generation.
* *Key Features:* Outputs interactive terminal ASCII grids or high-resolution PNG map images complete with a detailed textual gazetteer describing every landmark and town.


* **[`dungeon/dungeon.py`](https://www.google.com/search?q=dungeon/dungeon.py)**
* *What it does:* Generates intricate underground complexes using 5 distinct procedural dungeon generation algorithms, complete with shadowcasting field-of-view (FOV) rendering.
* *Key Features:* Includes a fully playable terminal roguelike adventure mode (WASD / arrow keys / vi-keys) and an automated A* pathfinding bot mode that explores and clears dungeons autonomously.


* **[`namegen/namegen.py`](https://www.google.com/search?q=namegen/namegen.py)**
* *What it does:* Serves as an advanced procedural naming engine offering 69 distinct name generation strategies.
* *Key Features:* Includes 13 invented phonotactic "languages" with realistic phonetic rules, Markov chain transition models, structural formatting templates (`"{title} {elvish} of {town}"`), and custom training capabilities on your own text files.



### 3. Games, Puzzles & Procedural Text

* **[`maze/maze.py`](https://www.google.com/search?q=maze/maze.py)**
* *What it does:* Generates and solves mazes across 9 advanced generation algorithms (Backtracker, Prim, Kruskal, Wilson, Aldous-Broder, Hunt-and-Kill, Sidewinder, Binary Tree, Recursive Division) and 6 solving strategies.
* *Key Features:* Supports 7 geometric shapes (rectangular, circular, ringed, diamond, triangular, cross, heart), live terminal animation, braiding loops, rigor bias statistics, SVG/PNG export, and a fully playable interactive mode with hint systems.


* **[`story/storyspark.py`](https://www.google.com/search?q=story/storyspark.py)**
* *What it does:* A lightweight Tracery-style generative grammar engine pre-loaded with 30 narrative generator templates.
* *Key Features:* Instantly spins up story outlines, quest hooks, fantasy monster stats, and ancient prophecies. Features linguistic modifiers (`.capitalize`, `.a`, `.s`), variable state persistence, dice notation parsing (`{3d6}`), numerical ranges, inline choices, weighted symbol resolution, and a Markov text babbler.



### 4. Mathematics, Fractals & Visualizations

* **[`math/fractals/fractals.py`](https://www.google.com/search?q=math/fractals/fractals.py)**
* *What it does:* Renders 9 complex fractal families (Mandelbrot, Julia, Burning Ship, Tricorn, Celtic, Multibrot, Phoenix, Newton, Magnet) with 5 coloring modes and 12 distinct color palettes.
* *Key Features:* Leverages multi-core CPU parallelism, hand-written raw PNG encoders, a custom LZW animated-GIF encoder, and an interactive real-time explorer mode with pan, zoom, and dynamic Julia set projection.


* **[`math/lsystem/lsystem.py`](https://www.google.com/search?q=lsystem.py)**
* *What it does:* Simulates 24 botanical and mathematical L-system presets (dragon curves, Hilbert space-filling curves, branching fractals, and plant models).
* *Key Features:* Supports stochastic rewriting rules, terminal Braille canvas rendering, and high-resolution vector SVG and raster PNG image generation.


* **[`math/sortviz/sortviz.py`](https://www.google.com/search?q=sortviz.py)**
* *What it does:* Visualizes 18 classic sorting algorithms directly in the terminal interface.
* *Key Features:* Race multiple algorithms side-by-side in real-time, execute comprehensive benchmark suites across various array sizes, or sonify sorting comparisons into rhythmic WAV audio files.



### 5. Simulations, Cellular Automata & Cryptography

* **[`simulations/simlab.py`](https://www.google.com/search?q=simulations/simlab.py)**
* *What it does:* Executes 7 hypnotic mathematical and physical terminal simulations.
* *Key Features:* Covers Boids flocking behavior, N-body gravitational orbital mechanics (figure-eight choreography), chaotic double pendulums, sandpile avalanche models, Lorenz strange attractors, reaction-diffusion chemical systems, and Ising magnetic field models.


* **[`simulations/lifegame.py`](https://www.google.com/search?q=simulations/lifegame.py)**
* *What it does:* Simulates Conway’s Game of Life alongside 10 alternative cellular automata rulesets (HighLife, Seeds, Day & Night, etc.).
* *Key Features:* Includes 13 classic historical patterns, RLE pattern file import, Wolfram 1D elementary cellular automata, Langton’s ant, Brian's Brain, automatic pattern recognition, and GIF/PNG export.


* **[`utilities/cipher.py`](https://www.google.com/search?q=cipher.py)**
* *What it does:* Implements 27 classical cryptographic ciphers and text encodings.
* *Key Features:* Features a fully authentic Enigma M3 machine simulation (configurable rotors I-VIII, ring settings, and plugboard pairs) alongside automated cryptanalytic crackers for Caesar, Vigenère, and monoalphabetic substitution ciphers.


* **[`utilities/randomizer.py`](https://www.google.com/search?q=utilities/randomizer.py)**
* *What it does:* A massive Swiss-army knife utility offering 94 distinct subcommands.
* *Key Features:* Includes advanced dice rolling (`4d6kh3`), 18 statistical probability distributions, cryptographically secure password and passphrase generation, test data synthesis (fake emails, phone numbers, UUIDs), card game simulations, Sudoku puzzle generation, and over 1,700 built-in trivia items.



---

## System Requirements & Prerequisites

* **Python 3.8+** (Fully compatible with Python 3.8 through Python 3.13+).
* **Zero Dependencies:** Absolutely no `pip install`, no external packages, and no virtual environment setup required. Everything operates entirely on built-in standard library modules (`os`, `sys`, `math`, `wave`, `struct`, `argparse`, `random`, `secrets`, etc.).

---

## Quick Start Guide (VS Code & Terminal)

1. **Install Python & VS Code:** Download and install [Python](https://www.python.org/downloads/) (on Windows, ensure you check the box to **Add python.exe to PATH**), alongside VS Code and its official **Python** extension.
2. **Open the Repository:** Clone or extract this repository, open VS Code, and select **File → Open Folder…** to load the project root directory.
3. **Open a Terminal:** Press Ctrl+`** to open the integrated terminal. On Windows, if `python`is not recognized by your shell, use`py`.

### Example Execution Commands

```bash
python audio/beatbox/beatbox.py "fast aggressive trap 8 bars with lip roll and laser"
python namegen/namegen.py elf 10
python maze/maze.py --shape heart -W 30 -H 26 --animate
python math/fractals/fractals.py --preset seahorse --palette ultra
python story/storyspark.py story
python utilities/randomizer.py dice d20+5 adv

```

### Advanced Usage & Input Patterns

* **Double-Click Execution (Windows):** You can double-click any `.py` script directly in your desktop file explorer. The script will execute its default demonstration, keep the terminal window open, and prompt you interactively for further options (`q` to quit).
* **File-Based Prompts:** For extensive prompts or configurations, save your text into a file (e.g., `@prompt.md` or `@prompt.txt`) and pass it directly as an argument (e.g., `python audio/beatbox/beatbox.py @prompt.md`).
* **Multiline Interactive Stdin (`<<<`):** When running a script interactively, typing `<<<` allows you to paste multi-line inputs freely, finishing your block with a final line containing `END`.
* **Built-in Help & Lists:** Every single script supports the `--help` flag for comprehensive documentation, and most feature `--list` to inspect available presets, styles, and parameters.

---

## The Second Batch: Advanced Command Suite

```bash
python simulations/lifegame.py gosper-gun --gens 200                         # Glider gun simulation; add --gif gun.gif to export animation
python simulations/lifegame.py --rule highlife --random 0.3 --torus
python simulations/lifegame.py --wolfram 110 ; python simulations/lifegame.py --ant
python utilities/cipher.py vigenere "ATTACKATDAWN" -k LEMON ; python utilities/cipher.py vigenere "<ciphertext>" --crack
python utilities/cipher.py enigma "HELLOWORLD" --rotors I,II,III --start AAA --plug "AB CD"
python utilities/cipher.py --selftest                                      # Verifies internal correctness against published test vectors
python math/sortviz/sortviz.py --race quick merge heap shell bubble
python math/sortviz/sortviz.py --bench --sizes 100,1000 ; python math/sortviz/sortviz.py merge --audio merge.wav
python math/lsystem/lsystem.py -p dragon -n 12 --png dragon.png --color rainbow
python math/lsystem/lsystem.py --axiom F --rule "F=F+F-F-F+F" --angle 90 -n 3
python audio/synth/synth.py "sad minor piano 70 bpm" --midi tune.mid
python worldgen/worldgen.py --seed 42 --png world.png --size 200 --erosion 20 ; python worldgen/worldgen.py --gazetteer
python dungeon/dungeon.py --play                                           # WASD / arrows / hjkl movement; add --bot to let an A* solver explore
python simulations/simlab.py pendulum --butterfly ; python simulations/simlab.py nbody ; python simulations/simlab.py gray --preset worms

```

### Technical Notes & Cryptographic Guarantees

* **Substitution Cracker:** The substitution cipher cracker utilizes a sophisticated hill-climbing optimization heuristic. It successfully recovers the vast majority of letters in English ciphertexts of ~250 characters or more, rather than offering instant mathematical determinism.
* **Audio & Sonification Integrity:** `synth.py` and `sortviz.py --audio` generate fully compliant WAV and MIDI binary streams verified for structural chunk integrity and safe amplitude limiting; artistic arrangement and musical taste remain subjective.
* **Enigma Historical Accuracy:** The Enigma M3 cryptographic engine rigorously adheres to historical specifications, matching published test vectors down to the mechanical middle-rotor double-step anomaly.

---

## Automated Test Suite

To verify system integrity, determinism, and mathematical correctness across every single script in the repository, execute the complete unit test runner:

```bash
python -m unittest discover -s tests -v

```

The comprehensive test suite covers voice synthesis rendering, seed determinism, maze perfection, solver consensus, LZW compression round-trips for custom GIF writers, grammar closure checks, dice/poker/sudoku rules enforcement, and automated static syntax guards ensuring all f-strings remain strictly safe on Python 3.8+. Continuous integration (CI) pipelines automatically execute these validations across Linux, Windows, and macOS on multiple Python versions.

---

## Contributing

We warmly welcome new contributions, toys, and improvements! Please review [CONTRIBUTING.md](https://www.google.com/search?q=CONTRIBUTING.md) for detailed structural guidelines, thematic folder conventions, branching models, and coding style requirements before submitting a pull request.

---

## License

This project is open-source software released under the terms of the **MIT License**—see [LICENSE](https://www.google.com/search?q=LICENSE) for full legal details.
