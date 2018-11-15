import svgwrite
import enum, math

################
# Tree utility functions
#
# For generically handling the various kinds of tree-like things that can be
# passed to this module
################

def treelet_split_str(t):
    # treat strings as leaf nodes.
    if isinstance(t, str):
        return (t, tuple())
    else:
        return None

def treelet_split_nltk(t):
    # nltk.Tree API: the parent is in label(). The children are elements of the
    # object itself, which inherits from list.
    try:
        h = t.label()
        return (h, list(t))
    except:
        return None

def treelet_split_list(t):
    # treat a list as a lisp-like tree structure, i.e. each subtree is a list
    # of the parent followed by any children.
    # A 0-length list is treated as an empty leaf node.
    try:
        if (len(t) == 0):
            return ("", tuple())
        else:
            return (t[0], t[1:])
    except:
        return None

def treelet_split_fallback(t):
    # fallback to str(). TODO: enhance, or remove?
    return (str(t), tuple())

def tree_split(t):
    """Splits `t` into a parent and an iterable of children, possibly empty."""
    split = treelet_split_str(t)
    if split is not None:
        return split
    split = treelet_split_nltk(t)
    if split is not None:
        return split
    split = treelet_split_list(t)
    if split is not None:
        return split
    return treelet_split_fallback(t)   

def tree_cxr(t, i):
    return tree_split(t)[i]

def tree_car(t):
    """What is the parent of a tree-like object `t`?
    Try to adapt to various possibilities, including nltk.Tree."""
    return tree_cxr(t, 0)

def tree_cdr(t):
    """What are the children of a tree-like object `t`?
    Try to adapt to various possibilities, including nltk.Tree."""
    return tree_cxr(t, 1)

def is_leaf(t):
    return len(tree_cdr(t)) == 0

def tree_depth(t):
    """What is the max depth of t?"""
    # n.b. car is always length 1 the way trees are currently parsed
    subdepth = 0
    for subtree in tree_cdr(t):
        subdepth = max(subdepth, tree_depth(subtree))
    return subdepth + 1

def leaf_iter(t):
    parent, children = tree_split(t)
    if len(children) == 0:
        yield parent
    for c in children:
        yield from leaf_iter(c)

def common_parent(path1, path2):
    for i in range(min(len(path1), len(path2))):
        if path1[i] != path2[i]:
            return tuple(path1[0:i])
    if len(path1) < len(path2):
        return path1
    else:
        return path2

################
# Tree layout options
################

# either EVEN or NODES usually looks best with abstract trees; TEXT usually
# looks the best for trees with real node labels, and so it is the default.
class HorizSpacing(enum.Enum):
    TEXT = 0  # Space daughter nodes proportional to label width
    EVEN = 1  # Space daughter nodes evenly
    NODES = 2 # Space daughter nodes based on number of leaf nodes

HorizOptions = HorizSpacing # backwards compatibility

class VertAlign(enum.Enum):
    TOP = 0    # align nodes at the top of the level's height
    CENTER = 1 # align nodes to the center of the level's height. Default.
    BOTTOM = 2 # align nodes with the bottom of the level's height
    FULL = 3   # all nodes take up the full level height. Currently, this aligns
               # text to the top, maybe would be better if centered?

def em(n):
    return "%gem" % n

def perc(n):
    return "%g%%" % n

class TreeOptions(object):
    def __init__(self, horiz_spacing=HorizSpacing.TEXT,
                       vert_align=VertAlign.CENTER,
                       leaf_padding=2,
                       distance_to_daughter=2,
                       debug=False,
                       leaf_nodes_align=False,
                       global_font_style="font-family: times, serif; font-weight:normal; font-style: normal; font-size: 12pt;",
                       average_glyph_width=2.0,
                       descend_direct=True):
        self.horiz_spacing = horiz_spacing
        self.vert_align = vert_align
        self.leaf_padding = leaf_padding
        self.distance_to_daughter = distance_to_daughter
        self.debug = debug
        self.leaf_nodes_align = leaf_nodes_align
        self.global_font_style = global_font_style
        # 2.0 default value is a heuristic -- roughly, 2 chars per em
        self.average_glyph_width = average_glyph_width
        # for multi-level descents, do we just draw a direct (usually shraply
        # angled) line, or do we draw an angled line one level, and a straight
        # line for the rest? Node position is unaffected.
        self.descend_direct = descend_direct

        # not technically an option, but convenient to store here for now...
        self.max_depth = 0

    def label_width(self, label):
        return (len(str(label)) + self.leaf_padding) / self.average_glyph_width

    def tree_height(self, t):
        """Calculate tree height, in ems. Takes into account multi-line leaf
        nodes."""
        # TODO: generalize to multi-line nodes of all kinds.
        parent, children = tree_split(t)
        if len(children) == 0:
            return len(parent.split("\n"))
        subheight = 0
        for subtree in children:
            subheight = max(subheight, self.tree_height(subtree))
        return subheight + self.distance_to_daughter + 1

def leaf_nodecount(t, options=None):
    """How many nodes wide are all the leafs? Will add padding."""
    if options is None:
        options=TreeOptions()
    parent, children = tree_split(t)
    if len(children) == 0:
        return 1 + options.leaf_padding
    subwidth = 0
    for subtree in children:
        subwidth += leaf_nodecount(subtree, options)
    return subwidth

################
# Tree layout and SVG generation
################

class NodePos(object):
    def __init__(self, svg, x, y, width, height, depth):
        self.x = x
        self.y = y
        self.width = max(width, 1) # avoid divide by 0 errors
        self.inner_width = width
        self.height = height
        self.inner_height = height
        self.depth = depth
        self.svg = svg
        self.text = svg

    def width(self):
        return self.width

    def height(self):
        return self.height

    def get_svg(self):
        # TODO: generalize this / make it less hacky
        self.svg["y"] = em(self.y)
        return self.svg

    def __repr__(self):
        return self.text

    @classmethod
    def from_label(cls, label, depth, options):
        y = 1
        svg_parent = svgwrite.container.SVG(x=0, y=0, width="100%")
        if len(label) == 0:
            return NodePos(svg_parent, 50, 0, options.label_width(""), 0, depth)
        for line in label.split("\n"):
            svg_parent.add(svgwrite.text.Text(line, insert=("50%", em(y)),
                                                    text_anchor="middle"))
            y += 1
        width = max([options.label_width(line) for line in label.split("\n")])
        result = NodePos(svg_parent, 50, 0, width, y-1, depth)
        result.text = label
        return result

class TreeLayout(object):
    """Container class for storing a tree layout state."""
    def __init__(self, t, options=None):
        if options is None:
            options = TreeOptions()
        self.level_heights = dict()
        self.level_ys = dict({0: 0})
        self.max_width = 1
        self.extra_y = 1.0
        self.depth = 0
        self.options = options
        self.tree = t
        self.annotations = list() # list of svgwrite objects
        self._do_layout(t) # initializes self.layout

    def __str__(self):
        return str(self.tree)

    def __repr__(self):
        # TODO: options repr? Not really very important? This function is mostly
        # here so that raw object ids don't contribute to .ipynb diffs.
        return "TreeLayout(%s)" % repr(self.tree)

    def relayout(options=None, **args):
        if options is None:
            options = TreeOptions(**args)
        # TODO: redo in self, instead?
        return TreeLayout(self.tree, options=options)

    ######## Annotations

    def box_constituent(self, path, stroke="none", rounding="5pt",
                        stroke_width="0.5pt", fill="gray", fill_opacity=0.15):
        (x, y, width, height) = self.subtree_bounds(path)
        rect = svgwrite.shapes.Rect(insert=(perc(x), em(y)),
                                    size=(perc(width), em(height)),
                                    stroke=stroke,
                                    fill=fill,
                                    fill_opacity=fill_opacity,
                                    rx=rounding,
                                    ry=rounding,
                                    stroke_width=stroke_width)
        self.annotations.append(rect)

    def underline_constituent(self, path, stroke="black", stroke_width="0.5pt",
                              stroke_opacity=1.0):
        (x, y, width, height) = self.subtree_bounds(path)
        underline = svgwrite.shapes.Line(start=(perc(x), em(y + height)),
                                         end=(perc(x + width), em(y + height)),
                                         stroke=stroke,
                                         stroke_width=stroke_width,
                                         stroke_opacity=stroke_opacity)
        self.annotations.append(underline)

    def _movement_find_y(self, x1, x2, y):
        # try to keep movement arrows from obscuring each other; a bit hacky
        try:
            self._movement_arrows
        except:
            self._movement_arrows = list()
        for existing_x1, existing_x2, existing_y in self._movement_arrows:
            if math.isclose(y, existing_y) and (x1 < existing_x2 or x2 > existing_x1):
                return self._movement_find_y(x1, x2, y + 0.5)
        self._movement_arrows.append((x1, x2, y))
        return y

    def deepest_intervening_leaf(self, path1, path2):
        """Find the deepest leaf node between nodes characterized by two paths.
        """
        return max([n.depth for n in self.leaf_span_iter(path1, path2)])

    def movement_arrow(self, path1, path2, stroke="black", stroke_width="0.5pt"):
        n1_pos = self.subtree_bounds(path1)
        n2_pos = self.subtree_bounds(path2)
        n1_y = n1_pos[1] + n1_pos[3]
        n1_x = n1_pos[0] + n1_pos[2] / 2
        n2_y = n2_pos[1] + n2_pos[3]
        n2_x = n2_pos[0] + n2_pos[2] / 2
        #y_target = max(n1_y, n2_y) + 1.0
        y_depth = self.deepest_intervening_leaf(path1, path2)
        y_target = self.y_distance(0, y_depth) + self.level_heights[y_depth] + 1.2
        y_target = self._movement_find_y(min(n1_x, n2_x), max(n1_x, n2_x), y_target)
        self.extra_y = max(self.extra_y, 2)
        #TODO polyline? need to use a viewbox
        self.annotations.append(svgwrite.shapes.Line(
            start=(perc(n1_x), em(n1_y)), end=(perc(n1_x), em(y_target)),
            stroke=stroke, stroke_width=stroke_width))
        self.annotations.append(svgwrite.shapes.Line(
            start=(perc(n1_x), em(y_target)), end=(perc(n2_x), em(y_target)),
            stroke=stroke, stroke_width=stroke_width))
        self.annotations.append(svgwrite.shapes.Line(
            start=(perc(n2_x), em(y_target)), end=(perc(n2_x), em(n2_y)),
            stroke=stroke, stroke_width=stroke_width))
        #TODO markers for arrowheads? these arrowheads are a bit dumb
        self.annotations.append(svgwrite.shapes.Line(
            start=(perc(n2_x), em(n2_y)), end=(perc(n2_x + 1), em(n2_y + 0.45)),
            stroke=stroke, stroke_width=stroke_width))
        self.annotations.append(svgwrite.shapes.Line(
            start=(perc(n2_x), em(n2_y)), end=(perc(n2_x - 1), em(n2_y + 0.45)),
            stroke=stroke, stroke_width=stroke_width))


    ######## Layout information

    def height(self):
        return (sum([self.level_ys[l] for l in range(self.depth + 1)]) +
                self.level_heights[self.depth] +
                self.extra_y)

    def width(self):
        return self.max_width

    def label_y_dodge(self, node=None, level=None, height=None):
        """Calculate the y positions of a label, relative to other labels in the
        same row. Returns a tuple of the top dodge, and the bottom dodge, as
        positive numbers."""
        if node is None:
            node = NodePos(None, 0, 0, 0, 0, 0)
        if level is None:
            level = node.depth
        if height is None:
            height = node.height
        if self.options.vert_align == VertAlign.TOP:
            return (0, self.level_heights[level] - height)
        elif self.options.vert_align == VertAlign.BOTTOM:
            return (self.level_heights[level] - height, 0)
        elif self.options.vert_align == VertAlign.CENTER:
            dodge = (self.level_heights[level] - height) / 2.0
            return (dodge, dodge)
        else:
            return (0,0)

    def y_distance(self, level_a, level_b):
        """What is the total y distance between levels a and b, starting from
        the containing svg for level_a?"""
        # level_ys is a dict, so can't use slicing
        level_b = min(self.depth, level_b)
        return sum([self.level_ys[l] for l in range(level_a + 1, level_b + 1)])

    def layout_iter(self, path):
        """An iterator over every position in the layout, where the head is
        at position 0, and any children follow. Will throw AttributeError on an
        invalid path at the point in iteration where the path is invalid. (If
        you want to validate a path, you can do this by converting to a list.)
        """
        node = self.layout
        yield node
        i = 0
        for c in path:
            parent, children = node[0], node[1:]
            try:
                node = children[c]
            except IndexError:
                raise AttributeError(
                    "Invalid tree path at index %d (daughter %d)" % (i, c))
            yield node
            i += 1

    def node_iter(self, path):
        """An iterator over every node in the layout. Will throw AttributeError
        on an invalid path at the point in iteration where the path is invalid.
        """
        for n in self.layout_iter(path):
            yield n[0]

    def leaf_span_iter(self, path1, path2):
        """Iterate over a potentially non-constituent sequences of leaves
        delimited by path1 and path2. Includes any leaves under the paths, and
        so therefore will be non-empty (if the tree is non-empty). The paths
        may be in either order, but the iteration will always be left-to-right.
        """
        branch = common_parent(path1, path2)
        # the complication comes in here because the path bounds might not
        # specify a constituent (in fact they typically won't unless they are
        # equal).
        constituent_leaves = list(leaf_iter(self.sublayout(branch)))
        path1_leaves = list(leaf_iter(self.sublayout(path1)))
        path2_leaves = list(leaf_iter(self.sublayout(path2)))
        for i in range(len(constituent_leaves)):
            if constituent_leaves[i] == path1_leaves[0]:
                path1_i = i
            if constituent_leaves[i] == path2_leaves[0]:
                path2_i = i
        if path1_i < path2_i:
            left = path1_i
            right = path2_i + len(path2_leaves)
        else:
            left = path2_i
            right = path1_i + len(path1_leaves)
        return iter(constituent_leaves[left:right])

    def sublayout(self, path):
        """Find the position in the layout given by a tree path, i.e. a sequence
        of daughter indices (indexed from 0). Will throw AttributeError on an
        invalid path."""
        return list(self.layout_iter(path))[-1]

    def nmost_path(self, path, n):
        """Find the deepest path from starting position `path` that can be
        reached via daughter index n repeatedly."""
        path = list(path)
        t = self.sublayout(path)
        parent, children = t[0], t[1:]
        i = len(path)
        while i < self.depth + 1:
            try:
                parent, children = children[n][0], children[n][1:]
                path = path + [n]
            except IndexError:
                break
        return path

    def leftmost_path(self, path=()):
        """Find the deepest path starting position `path` that can be
        found by going left repeatedly."""
        return self.nmost_path(path, 0)

    def rightmost_path(self, path=()):
        """Find the deepest path starting position `path` that can be
        found by going right repeatedly."""
        return self.nmost_path(path, -1)

    def node_x_vals(self, path):
        """Find, relative to the outer svg, the x position and width for node
        at position `path`. Both values are in percentages."""
        left = 0.0
        width = 100.0
        i = 0
        for node in self.node_iter(path):
            left += node.x * width / 100.0
            width = width * node.width / 100.0
        return left, width

    def subtree_bounds(self, path):
        """Found the bounding box for a subtree whose parent is at position
        `path`, in the format of a tuple (x, y, width, height). X values are
        in percentages, and Y values are in ems. The values are relative to the
        outermost svg."""
        parent = self.sublayout(path)
        deepest = max([l.depth for l in leaf_iter(parent)])
        left_path = self.leftmost_path(path)
        right_path = self.rightmost_path(path)
        x = self.node_x_vals(left_path)[0]
        width = sum(self.node_x_vals(right_path)) - x
        y = self.y_distance(0, parent[0].depth)
        height = (self.y_distance(parent[0].depth, deepest)
                  + self.level_heights[deepest]
                  + 0.5)
        return (x, y, width, height)

    ########### Layout stuff, mostly internal

    def _do_layout(self, t):
        self.level_heights = dict()
        self.level_ys = dict({0: 0})
        self.depth =  tree_depth(t) - 1
        for i in range(self.depth + 1):
            self.level_heights[i] = 0
        parsed = self._build_initial_layout(t)
        self._calc_level_ys()
        if len(parsed) > 0:
            self.max_width = parsed[0].width
        else:
            self.max_width = 0
        if len(parsed) > 0:
            parsed[0].width = 100.0
            parsed[0].x = 0
        self._normalize_widths(parsed)
        self._normalize_y(parsed)
        #self._adjust_leaf_nodes(parsed)
        self.layout = parsed

    def _build_initial_layout(self, t, level=0):
        # initialize raw widths and node heights, both in em at this point.
        # also initialize level_heights for all levels, and depth values for
        # nodes.
        parent, children = tree_split(t)

        # if leaf nodes align, all leaf nodes contribute to height for the
        # deepest level, not their actual depth
        if len(children) == 0 and self.options.leaf_nodes_align:
            level = self.depth
        node = NodePos.from_label(parent, level, self.options)

        self.level_heights[level] = max(self.level_heights[level], node.height)
        result_children = [self._build_initial_layout(c, level+1)
                                                            for c in children]
        node.width = max(node.width, sum([c[0].width for c in result_children]))
        return [node] + result_children

    def _subtree_proportions(self, l):
        if len(l) == 0:
            return list()
        if (self.options.horiz_spacing == HorizOptions.EVEN):
            return [100.0 / len(l)] * len(l)
        else: # TEXT or NODES
            widths = list()
            sum = 0
            for t in l:
                if self.options.horiz_spacing == HorizOptions.TEXT:
                    widths.append(t[0].width) # precalculated
                else: # NODES
                    widths.append(leaf_nodecount(t, self.options))
                sum += widths[-1]

            # normalize to percentages
            for i in range(len(widths)):
                widths[i] = widths[i] * 100.0 / sum
            return widths

    def _normalize_widths(self, t):
        # normalize widths to percentages.
        parent, children = t[0], t[1:]
        for c in children:
            self._normalize_widths(c)
        widths = self._subtree_proportions(children)
        x_pos = 0
        for i in range(len(children)):
            children[i][0].width = widths[i]
            children[i][0].x = x_pos
            x_pos += widths[i]

    def _calc_level_ys(self):
        # Calculate the y position of each row, relative to containing svg
        self.level_ys[0] = 0
        for i in range(1, self.depth + 1):
            self.level_ys[i] = (self.options.distance_to_daughter
                                + self.level_heights[i - 1])

    def _normalize_y(self, t):
        # calculate y distances for each level. This is done on a second pass
        # because it needs level_heights to be initialized.
        parent, children = t[0], t[1:]
        if (self.options.vert_align == VertAlign.FULL):
            parent.height = self.level_heights[parent.depth]
        parent.y = self.label_y_dodge(node=parent)[0]
        for c in children:
            self._normalize_y(c)

    ######### SVG building

    def _svg_add_subtree(self, svg_parent, t):
        # This uses several tricks to simulate the ways in which relative
        # positioning in raw SVG is hard:
        # 1. For x, use percentage-based positioning relative to nested `svg`
        #    elements. Every subtree has its own `<svg />` container, and the
        #    parent node is at `(50%, 1em)` relative to that container. There
        #.   are also some (simple) heuristics for estimating text width.
        # 2. Do all y positioning in `em`s. This is because it is impossible 
        #    to accurately get text sizes ahead of time (without somehow
        #    doing or simulating rendering) when generating SVG. So since `em`s
        #    ought to be relative to text size, only use that.
        from svgwrite.shapes import Line
        parent, children = t[0], t[1:]
        line_start = parent.y + parent.height
        if parent.height > 0:
            line_start += 0.2 # extra space for descenders
        svg_parent.add(parent.get_svg())
        for c in children:
            box_y = self.y_distance(parent.depth, c[0].depth)
            y_target = em(box_y + c[0].y)
            x_target = perc(c[0].x + c[0].width / 2)
            child = svgwrite.container.SVG(x=perc(c[0].x),
                                           y=em(box_y),
                                           width=perc(c[0].width))
            if self.options.debug:
                child.add(svgwrite.shapes.Rect(insert=("0%","0%"),
                                               size=("100%", "100%"),
                                               fill="none", stroke="red"))
            svg_parent.add(child)

            if c[0].depth > parent.depth + 1 and not self.options.descend_direct:
                # we are skipping level(s). Find the y position that an empty
                # node on the next level would have.
                intermediate_y = em(self.label_y_dodge(level=parent.depth+1,
                                                     height=0)[0]
                                  + self.y_distance(parent.depth, parent.depth+1))
                # TODO: do as Path?
                svg_parent.add(Line(start=("50%", em(line_start)),
                                    end=(x_target, intermediate_y),
                                    stroke="black"))
                svg_parent.add(Line(start=(x_target, intermediate_y),
                                    end=(x_target, y_target),
                                    stroke="black"))
            else:
                svg_parent.add(Line(start=("50%", em(line_start)),
                                    end=(x_target, y_target),
                                    stroke="black"))

            self._svg_add_subtree(child, c)

    def svg_build_tree(self, name="tree"):
        """Build an `svgwrite.Drawing` object based on the layout calculated
        when initializing the object."""

        # estimate canvas size based on depth + leaf widths. This probably isn't
        # very accurate in some limiting cases...but to do any better would need
        # either some way of simulating text rendering (inkscape?) or javascript
        # code that adjusts the tree spacing dynamically after the initial
        # rendering. Here we try to do as good as possible with pure python =>
        # SVG.

        width = self.max_width
        height = self.height()
        tree = svgwrite.Drawing(name, (em(width), em(height)),
            style=self.options.global_font_style)
        if self.options.debug:
            tree.add(tree.rect(insert=(0,0), size=("100%", "100%"),
                fill="none", stroke="lightgray"))
            for i in range(1, int(width)):
                tree.add(tree.line(start=(em(i), 0),
                                   end=(em(i), "100%"),
                                   stroke="lightgray"))
            for i in range(1, int(height)):
                tree.add(tree.line(start=(0, em(i)),
                                   end=("100%", em(i)),
                                   stroke="lightgray"))
        self._svg_add_subtree(tree, self.layout)
        for a in self.annotations:
            tree.add(a)
        return tree

    def get_svg(self):
        tree = self.svg_build_tree()
        for a in self.annotations:
            tree.add(a)
        return tree

    def _repr_svg_(self):
        return self.get_svg().tostring()

################
# Module-level api
################

def draw_tree(*t, options=None, **opts):
    """Return an object that implements SVG tree rendering, for display
    in a Jupyter notebook."""
    from IPython.core.display import SVG
    if options is None:
        options = TreeOptions(**opts)
    if len(t) == 1:
        t = t[0]
    return TreeLayout(t, options=options)

nltk_tree_options = TreeOptions()

def monkeypatch_nltk():
    import nltk
    global nltk_tree_options
    nltk.Tree._repr_svg_ = lambda self: TreeLayout(self, options=nltk_tree_options)._repr_svg_()

def module_setup():
    try:
        monkeypatch_nltk()
    except:
        pass

module_setup()

