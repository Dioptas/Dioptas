//! Native window reductions and a bounded arithmetic-only expression grammar.
use std::collections::{BTreeMap, BTreeSet};
pub(crate) const REDUCTIONS: [&str; 6] = ["sum", "mean", "max", "area", "center", "width"];
pub(crate) struct Window {
    indices: Vec<usize>,
    x: Vec<f64>,
    kind: String,
    background: bool,
}
impl Window {
    pub fn new(x: &[f64], low: f64, high: f64, kind: &str, background: bool) -> Self {
        let indices = x
            .iter()
            .enumerate()
            .filter_map(|(i, &x)| (x > low && x < high).then_some(i))
            .collect::<Vec<_>>();
        let selected = indices.iter().map(|&i| x[i]).collect();
        Self {
            indices,
            x: selected,
            kind: kind.into(),
            background,
        }
    }
    pub fn reduce(&self, y: &[f64]) -> f64 {
        if self.indices.is_empty() {
            return f64::NAN;
        }
        if !self.background && ["sum", "mean"].contains(&self.kind.as_str()) {
            let sum = self.indices.iter().map(|&i| y[i]).sum::<f64>();
            return if self.kind == "mean" {
                sum / self.indices.len() as f64
            } else {
                sum
            };
        }
        let yy = self.indices.iter().map(|&i| y[i]).collect::<Vec<_>>();
        reduce_samples(self.x.clone(), yy, &self.kind, self.background)
    }
}
pub(crate) fn reduce(
    x: &[f64],
    y: &[f64],
    low: f64,
    high: f64,
    kind: &str,
    background: bool,
) -> f64 {
    Window::new(x, low, high, kind, background).reduce(y)
}
fn reduce_samples(mut xx: Vec<f64>, mut yy: Vec<f64>, kind: &str, background: bool) -> f64 {
    let n = xx.len();
    if background || ["area", "center", "width"].contains(&kind) {
        if n < 2 {
            return f64::NAN;
        }
        let edge = ((n as f64 * 0.1).round_ties_even() as usize).max(1);
        let mean = |v: &[f64]| v.iter().sum::<f64>() / v.len() as f64;
        let (left, right) = (mean(&yy[..edge]), mean(&yy[n - edge..]));
        let (lx, rx) = (mean(&xx[..edge]), mean(&xx[n - edge..]));
        let slope = if rx == lx {
            0.0
        } else {
            (right - left) / (rx - lx)
        };
        for (x, y) in xx.iter().zip(&mut yy) {
            *y -= left + slope * (x - lx);
        }
    }
    match kind {
        "sum" => yy.iter().sum(),
        "mean" => yy.iter().sum::<f64>() / n as f64,
        "max" => {
            if yy.iter().any(|v| v.is_nan()) {
                f64::NAN
            } else {
                yy.into_iter().fold(f64::NEG_INFINITY, f64::max)
            }
        }
        "area" => {
            if n < 2 {
                f64::NAN
            } else {
                xx.windows(2)
                    .zip(yy.windows(2))
                    .map(|(x, y)| 0.5 * (x[1] - x[0]) * (y[0] + y[1]))
                    .sum::<f64>()
                    .abs()
            }
        }
        "center" => {
            let total = yy.iter().map(|v| v.max(0.0)).sum::<f64>();
            if n < 2 || total <= 0.0 || yy.iter().any(|v| v.is_nan()) {
                f64::NAN
            } else {
                xx.iter().zip(yy).map(|(x, y)| x * y.max(0.0)).sum::<f64>() / total
            }
        }
        "width" => {
            if n < 2 || yy.iter().any(|v| !v.is_finite()) {
                return f64::NAN;
            }
            if xx[0] > xx[n - 1] {
                xx.reverse();
                yy.reverse();
            }
            let apex = (0..n)
                .max_by(|&a, &b| yy[a].total_cmp(&yy[b]).then_with(|| b.cmp(&a)))
                .unwrap();
            let peak = yy[apex];
            if peak <= 0.0 {
                return f64::NAN;
            }
            let half = peak / 2.0;
            let crossing = |step: isize| -> Option<f64> {
                let mut i = apex as isize;
                while i + step >= 0 && i + step < n as isize {
                    let j = i + step;
                    let (a, b) = (i as usize, j as usize);
                    if yy[b] <= half {
                        let f = if yy[a] == yy[b] {
                            1.0
                        } else {
                            (yy[a] - half) / (yy[a] - yy[b])
                        };
                        return Some(xx[a] + f * (xx[b] - xx[a]));
                    }
                    i = j;
                }
                None
            };
            crossing(-1)
                .zip(crossing(1))
                .map_or(f64::NAN, |(a, b)| b - a)
        }
        _ => f64::NAN,
    }
}
#[derive(Clone, Debug)]
enum Node {
    Number(f64),
    Name(String),
    Text(String),
    Unary(bool, Box<Node>),
    Binary(String, Box<Node>, Box<Node>),
    Call(String, Vec<Node>),
}
#[derive(Clone, Debug)]
pub(crate) struct Expression {
    root: Node,
    nodes: usize,
}
struct Parser<'a> {
    text: &'a str,
    position: usize,
    nodes: usize,
}
impl<'a> Parser<'a> {
    fn whitespace(&mut self) {
        while self
            .text
            .as_bytes()
            .get(self.position)
            .is_some_and(u8::is_ascii_whitespace)
        {
            self.position += 1;
        }
    }
    fn take(&mut self, token: &str) -> bool {
        self.whitespace();
        if self.text[self.position..].starts_with(token) {
            self.position += token.len();
            true
        } else {
            false
        }
    }
    fn node(&mut self, n: Node) -> Result<Node, String> {
        self.nodes += 1;
        if self.nodes > 512 {
            return Err("Map expression exceeds 512 operations.".into());
        }
        Ok(n)
    }
    fn expression(&mut self, min: u8, depth: usize) -> Result<Node, String> {
        if depth > 64 {
            return Err("Map expression nesting exceeds 64 levels.".into());
        }
        self.whitespace();
        let mut left = if self.take("+") {
            let n = self.expression(3, depth + 1)?;
            self.node(Node::Unary(false, Box::new(n)))?
        } else if self.take("-") {
            let n = self.expression(3, depth + 1)?;
            self.node(Node::Unary(true, Box::new(n)))?
        } else if self.take("(") {
            let n = self.expression(0, depth + 1)?;
            if !self.take(")") {
                return Err("Unclosed expression parentheses.".into());
            }
            n
        } else {
            self.whitespace();
            let start = self.position;
            let bytes = self.text.as_bytes();
            let c = *bytes.get(start).ok_or("Incomplete map expression.")?;
            if c == b'\'' || c == b'"' {
                self.position += 1;
                let begin = self.position;
                while self
                    .text
                    .as_bytes()
                    .get(self.position)
                    .is_some_and(|&b| b != c)
                {
                    if self.text.as_bytes()[self.position] == b'\\' {
                        return Err("Overlay names must be literal text without escapes.".into());
                    }
                    self.position += 1;
                }
                let value = self.text[begin..self.position].to_string();
                if self.position >= self.text.len() {
                    return Err("Unclosed overlay name.".into());
                }
                self.position += 1;
                self.node(Node::Text(value))?
            } else if c.is_ascii_digit() || c == b'.' {
                self.position += 1;
                while let Some(&b) = self.text.as_bytes().get(self.position) {
                    if b.is_ascii_digit()
                        || b == b'.'
                        || b == b'e'
                        || b == b'E'
                        || ((b == b'+' || b == b'-')
                            && b"eE".contains(&self.text.as_bytes()[self.position - 1]))
                    {
                        self.position += 1;
                    } else {
                        break;
                    }
                }
                let n = self.text[start..self.position]
                    .parse::<f64>()
                    .map_err(|_| "Invalid expression number.")?;
                if !n.is_finite() {
                    return Err("Expression constants must be finite.".into());
                }
                self.node(Node::Number(n))?
            } else if c.is_ascii_alphabetic() || c == b'_' {
                self.position += 1;
                while self
                    .text
                    .as_bytes()
                    .get(self.position)
                    .is_some_and(|b| b.is_ascii_alphanumeric() || *b == b'_')
                {
                    self.position += 1;
                }
                let name = self.text[start..self.position].to_string();
                if self.take("(") {
                    let mut args = vec![];
                    if !self.take(")") {
                        loop {
                            args.push(self.expression(0, depth + 1)?);
                            if self.take(")") {
                                break;
                            }
                            if !self.take(",") {
                                return Err("Separate function arguments with commas.".into());
                            }
                        }
                    }
                    self.node(Node::Call(name, args))?
                } else {
                    self.node(Node::Name(name))?
                }
            } else {
                return Err(
                    "Only window names, numbers, arithmetic and supported functions are allowed."
                        .into(),
                );
            }
        };
        loop {
            self.whitespace();
            let op = ["**", "+", "-", "*", "/", "%"]
                .into_iter()
                .find(|op| self.text[self.position..].starts_with(op));
            let Some(op) = op else {
                break;
            };
            let precedence = match op {
                "+" | "-" => 1,
                "**" => 4,
                _ => 2,
            };
            if precedence < min {
                break;
            }
            self.position += op.len();
            let right = self.expression(if op == "**" { 3 } else { precedence + 1 }, depth + 1)?;
            left = self.node(Node::Binary(op.into(), Box::new(left), Box::new(right)))?;
        }
        Ok(left)
    }
}
impl Expression {
    pub fn rename(&self, old: &str, new: &str) -> String {
        fn render(n: &Node, old: &str, new: &str) -> String {
            match n {
                Node::Number(n) => n.to_string(),
                Node::Name(n) => {
                    if n == old {
                        new.into()
                    } else {
                        n.clone()
                    }
                }
                Node::Text(s) => format!("\"{s}\""),
                Node::Unary(negative, n) => format!(
                    "{}({})",
                    if *negative { "-" } else { "+" },
                    render(n, old, new)
                ),
                Node::Binary(op, a, b) => {
                    format!("({} {op} {})", render(a, old, new), render(b, old, new))
                }
                Node::Call(name, args) => format!(
                    "{}({})",
                    name,
                    args.iter()
                        .enumerate()
                        .map(|(i, a)| if name == "ovl" && i == 0 {
                            render(a, "", "")
                        } else {
                            render(a, old, new)
                        })
                        .collect::<Vec<_>>()
                        .join(", ")
                ),
            }
        }
        render(&self.root, old, new)
    }
    pub fn parse(text: &str) -> Result<Self, String> {
        if text.is_empty() || text.len() > 4096 {
            return Err("Map expression needs 1–4096 characters.".into());
        }
        let mut p = Parser {
            text,
            position: 0,
            nodes: 0,
        };
        let root = p.expression(0, 0)?;
        p.whitespace();
        if p.position != text.len() {
            return Err("Unexpected map expression text.".into());
        }
        Ok(Self {
            root,
            nodes: p.nodes,
        })
    }
    pub fn names(&self) -> BTreeSet<String> {
        fn visit(n: &Node, out: &mut BTreeSet<String>) {
            match n {
                Node::Name(n) => {
                    out.insert(n.clone());
                }
                Node::Unary(_, n) => visit(n, out),
                Node::Binary(_, a, b) => {
                    visit(a, out);
                    visit(b, out);
                }
                Node::Call(name, args) if name != "ovl" => {
                    for a in args {
                        visit(a, out);
                    }
                }
                Node::Call(name, args) if name == "ovl" && args.len() == 2 => visit(&args[1], out),
                _ => {}
            }
        }
        let mut set = BTreeSet::new();
        visit(&self.root, &mut set);
        set
    }
    pub fn evaluate(
        &self,
        layers: &BTreeMap<String, Vec<f64>>,
        count: usize,
        overlay: &impl Fn(&str, &str) -> Result<f64, String>,
    ) -> Result<Vec<f64>, String> {
        if self.nodes.saturating_mul(count) > 128_000_000 {
            return Err("Expression evaluation exceeds 128 million operations.".into());
        }
        let names = self.names();
        let default = if names.len() == 1 {
            names.first().map(String::as_str)
        } else {
            None
        };
        fn eval(
            n: &Node,
            layers: &BTreeMap<String, Vec<f64>>,
            count: usize,
            overlay: &impl Fn(&str, &str) -> Result<f64, String>,
            default: Option<&str>,
        ) -> Result<Vec<f64>, String> {
            Ok(match n {
                Node::Number(v) => vec![*v; count],
                Node::Name(n) => layers
                    .get(n)
                    .cloned()
                    .ok_or_else(|| format!("Unknown window {n}."))?,
                Node::Text(_) => {
                    return Err("Text is allowed only as an overlay name in ovl().".into());
                }
                Node::Unary(negative, a) => eval(a, layers, count, overlay, default)?
                    .into_iter()
                    .map(|v| if *negative { -v } else { v })
                    .collect(),
                Node::Binary(op, a, b) => eval(a, layers, count, overlay, default)?
                    .into_iter()
                    .zip(eval(b, layers, count, overlay, default)?)
                    .map(|(a, b)| match op.as_str() {
                        "+" => a + b,
                        "-" => a - b,
                        "*" => a * b,
                        "/" => a / b,
                        "**" => a.powf(b),
                        "%" => a - b * (a / b).floor(),
                        _ => f64::NAN,
                    })
                    .collect(),
                Node::Call(name, args) if name == "ovl" => {
                    fn get(n: &Node) -> Result<&str, &'static str> {
                        match n {
                            Node::Name(n) | Node::Text(n) => Ok(n.as_str()),
                            _ => Err("ovl() needs an overlay name and optional window name."),
                        }
                    }
                    if !(1..=2).contains(&args.len()) {
                        return Err("ovl() takes one or two arguments.".into());
                    }
                    let name = get(&args[0])?;
                    let window = if args.len() == 2 {
                        get(&args[1])?
                    } else {
                        default.ok_or("ovl(overlay) needs exactly one referenced window; specify ovl(overlay, window).")?
                    };
                    vec![overlay(name, window)?; count]
                }
                Node::Call(name, args) => {
                    let arity = match name.as_str() {
                        "abs" | "sqrt" | "log" | "log10" | "exp" => 1,
                        "minimum" | "maximum" => 2,
                        "clip" => 3,
                        _ => return Err("Unknown map expression function.".into()),
                    };
                    if args.len() != arity {
                        return Err(format!("{name}() expects {arity} arguments."));
                    }
                    let values = args
                        .iter()
                        .map(|n| eval(n, layers, count, overlay, default))
                        .collect::<Result<Vec<_>, _>>()?;
                    (0..count)
                        .map(|i| {
                            let a = values[0][i];
                            if a.is_nan() || values.iter().any(|v| v[i].is_nan()) {
                                return f64::NAN;
                            }
                            match name.as_str() {
                                "abs" => a.abs(),
                                "sqrt" => a.sqrt(),
                                "log" => a.ln(),
                                "log10" => a.log10(),
                                "exp" => a.exp(),
                                "minimum" => a.min(values[1][i]),
                                "maximum" => a.max(values[1][i]),
                                "clip" => a.max(values[1][i]).min(values[2][i]),
                                _ => f64::NAN,
                            }
                        })
                        .collect()
                }
            })
        }
        eval(&self.root, layers, count, overlay, default)
    }
}
pub(crate) fn identifier(name: &str) -> bool {
    !name.is_empty()
        && name.len() <= 128
        && name
            .bytes()
            .enumerate()
            .all(|(i, c)| c == b'_' || c.is_ascii_alphabetic() || (i > 0 && c.is_ascii_digit()))
        && ![
            "abs", "sqrt", "log", "log10", "exp", "clip", "minimum", "maximum", "ovl",
        ]
        .contains(&name)
}
