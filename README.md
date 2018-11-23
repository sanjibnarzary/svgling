# `svgling`: syntax trees in python + svg

**Author**: Kyle Rawlins, [kgr@jhu.edu](kgr@jhu.edu)

**Dependencies**: [`svgwrite`](https://pypi.org/project/svgwrite/), python 3

**Repository**: [https://github.com/rawlins/svgling/](https://github.com/rawlins/svgling/)

**Installation**: download and use setuptools, or `pip install svgling`

**License**: MIT License

The `svgling` package is a pure python package for doing single-pass rendering
of linguistics-style constituent trees into SVG. It is primarily intended for
integrating with Jupyter notebooks, but could be used to generate SVG diagrams
for all sorts of other purposes. It involves no javascript and so will work
in Jupyter without any plugins.

The basic interface is pretty simple: pass a tree object to `svgling.draw_tree`.

    import svgling
    svgling.draw_tree(("S", ("NP", ("D", "the"), ("N", "elephant")), ("VP", ("V", "saw"), ("NP", ("D", "the"), ("N", "rhinoceros")))))

This produces an SVG image like the following:

![example sentence](https://raw.githubusercontent.com/rawlins/svgling/master/demotree.svg?sanitize=true)

Core design principles/goals:

1. Be well suited for *programmatic* generation of tree diagrams (not just
hand-customized diagrams).
2. Be equally suited for theoretical linguistics and computational
linguistics/NLP, at least for cases where the latter is targeting constituent
trees. (This package is not aimed at dependency trees.)
3. Do as much as possible with pure python (as opposed to python+javascript, or
python+tk, or python+dot, or...).

The tree drawing code accepts two main tree formats: lisp-style trees made from
lists of lists (or tuples of tuples), with node labels as strings, or trees from
the [`nltk`](https://www.nltk.org/) package, i.e. objects instantiating the
[`nltk.tree.Tree`](https://www.nltk.org/_modules/nltk/tree.html) API.

Beyond basic tree-drawing, the package supports a number of flourishes like
movement arrows. For documentation and examples, see the three .ipynb files in
the root of this repository: (links below to nbviewer static rendered versions):

* [Overview.ipynb](https://nbviewer.jupyter.org/github/rawlins/svgling/blob/master/Overview.ipynb)
* [svgling Gallery.ipynb](https://nbviewer.jupyter.org/github/rawlins/svgling/blob/master/svgling%20Gallery.ipynb)
* [svgling Manual.ipynb](https://nbviewer.jupyter.org/github/rawlins/svgling/blob/master/svgling%20Manual.ipynb)

The package also by default monkey-patches `nltk.tree.Tree` so that Jupyter will
use svgling's rendering to display NLTK tree objects, instead of the built-in
`png` rendering (`svg` takes priority). For best `nltk` behavior, you may want
to in addition do the following when you import `svgling`:

    import nltk
    import svgling
    svgling.disable_nltk_png()

This call is effectively a safe wrapper around `del nltk.tree.Tree._repr_png_`.
The reason for doing this is that even though the `svg` is shown over `png`,
Jupyter still calls the `png` rendering function if there is one. On a mac,
deleting this function will prevent the annoying window-less app that shows up
(and stays as long as the kernel is running) when you view an `nltk` tree. On
64-bit windows, reportedly, the `png` rendering code in `nltk` causes problems,
and deleting this may avoid them. For headless uses of `nltk` on linux (see nltk
issue [#1887](https://github.com/nltk/nltk/issues/1887) for use-cases) deleting
this function will prevent errors resulting from tk not being able to open.

## Strengths and limitations

The `svgling` package does its rendering in one pass -- it takes a tree
structure as input, produces an svg output, and that's it. Because of this, it
is extremely simple to use in Jupyter, and no messing with plugins or Jupyter
settings should be necessary. Because it is SVG-based, scaling and embedding in
any web context should work smoothly. It also has minimal dependencies, just
one package that provides an abstraction layer over generating svg. (If you're
interested in programmatic diagramming in svg for Jupyter, I do recommend
[`svgwrite`](https://github.com/mozman/svgwrite), it's under active development
and has a very pleasant API + good documentation.)

Single-pass rendering also places limitations on what can be done. One of the
challenges is that it mostly uses absolute position, and the exact position and
width of text elements can't be determined without actually rendering to some
device and seeing what happens. In addition, the exact details of rendering are
in various ways at the mercy of the rendering device. This all means that
`svgling` uses a bunch of tricks to estimate node size and width, and won't
always be perfect on all devices. This situation also places some hard
limitations on how far `svgling` can be extended without adding javascript or
other multi-pass rendering techniques. For example, I would eventually like to
allow mathjax in nodes, and allow nodes with complex / multi-line shapes, but at
the moment this does not seem possible without javascript on the client side.

There are many things that it might be nice to add to this package; if you find
`svgling` useful, have any requests, or find any bugs, please let me know.
