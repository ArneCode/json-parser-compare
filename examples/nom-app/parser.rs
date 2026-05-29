//! JSON parser for the nom benchmark app.
//!
//! String parsing follows the fragment + `fold` approach from nom's
//! [`examples/string.rs`](https://github.com/rust-bakery/nom/blob/main/examples/string.rs),
//! adapted to `bytes::complete` and JSON escapes (`\u` + four hex digits).

use nom::{
    branch::alt,
    bytes::complete::{is_not, tag, take_while, take_while_m_n},
    character::complete::char,
    combinator::{cut, map, map_opt, opt, value, verify},
    error::{context, ContextError, ParseError},
    multi::{fold, separated_list0},
    number::complete::double,
    sequence::{delimited, preceded, separated_pair, terminated},
    IResult, Parser,
};
use std::collections::HashMap;

#[derive(Debug, PartialEq)]
pub enum JsonValue {
    Null,
    Str(String),
    Boolean(bool),
    Num(f64),
    Array(Vec<JsonValue>),
    Object(HashMap<String, JsonValue>),
}

fn sp<'a, E: ParseError<&'a str>>(i: &'a str) -> IResult<&'a str, &'a str, E> {
    take_while(|c: char| " \t\r\n".contains(c)).parse(i)
}

/// JSON `\uXXXX` escape (four hex digits).
fn parse_json_unicode<'a, E: ParseError<&'a str>>(input: &'a str) -> IResult<&'a str, char, E> {
    map_opt(
        take_while_m_n(4, 4, |c: char| c.is_ascii_hexdigit()),
        |hex: &str| u32::from_str_radix(hex, 16).ok().and_then(char::from_u32),
    )
    .parse(input)
}

fn parse_escaped_char<'a, E: ParseError<&'a str>>(input: &'a str) -> IResult<&'a str, char, E> {
    preceded(
        char('\\'),
        alt((
            value('\n', char('n')),
            value('\r', char('r')),
            value('\t', char('t')),
            value('\u{08}', char('b')),
            value('\u{0C}', char('f')),
            value('\\', char('\\')),
            value('/', char('/')),
            value('"', char('"')),
            preceded(char('u'), parse_json_unicode),
        )),
    )
    .parse(input)
}

fn parse_literal<'a, E: ParseError<&'a str>>(input: &'a str) -> IResult<&'a str, &'a str, E> {
    verify(is_not("\"\\"), |s: &str| !s.is_empty()).parse(input)
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum StringFragment<'a> {
    Literal(&'a str),
    EscapedChar(char),
}

fn parse_fragment<'a, E: ParseError<&'a str>>(input: &'a str) -> IResult<&'a str, StringFragment<'a>, E> {
    alt((
        map(parse_literal, StringFragment::Literal),
        map(parse_escaped_char, StringFragment::EscapedChar),
    ))
    .parse(input)
}

fn parse_json_string<'a, E: ParseError<&'a str>>(input: &'a str) -> IResult<&'a str, String, E> {
    let build_string = fold(
        0..,
        parse_fragment,
        String::new,
        |mut string, fragment| {
            match fragment {
                StringFragment::Literal(s) => string.push_str(s),
                StringFragment::EscapedChar(c) => string.push(c),
            }
            string
        },
    );

    delimited(char('"'), build_string, char('"')).parse(input)
}

fn boolean<'a, E: ParseError<&'a str>>(input: &'a str) -> IResult<&'a str, bool, E> {
    alt((value(true, tag("true")), value(false, tag("false")))).parse(input)
}

fn null<'a, E: ParseError<&'a str>>(input: &'a str) -> IResult<&'a str, (), E> {
    value((), tag("null")).parse(input)
}

fn string<'a, E: ParseError<&'a str> + ContextError<&'a str>>(
    i: &'a str,
) -> IResult<&'a str, String, E> {
    nom::error::context("string", parse_json_string).parse(i)
}

fn array<'a, E: ParseError<&'a str> + ContextError<&'a str>>(
    i: &'a str,
) -> IResult<&'a str, Vec<JsonValue>, E> {
    context(
        "array",
        preceded(
            char('['),
            cut(terminated(
                separated_list0(preceded(sp, char(',')), json_value),
                preceded(sp, char(']')),
            )),
        ),
    )
    .parse(i)
}

fn key_value<'a, E: ParseError<&'a str> + ContextError<&'a str>>(
    i: &'a str,
) -> IResult<&'a str, (String, JsonValue), E> {
    separated_pair(
        preceded(sp, string),
        cut(preceded(sp, char(':'))),
        json_value,
    )
    .parse(i)
}

fn hash<'a, E: ParseError<&'a str> + ContextError<&'a str>>(
    i: &'a str,
) -> IResult<&'a str, HashMap<String, JsonValue>, E> {
    context(
        "map",
        preceded(
            char('{'),
            cut(terminated(
                map(
                    separated_list0(preceded(sp, char(',')), key_value),
                    |pairs| pairs.into_iter().collect(),
                ),
                preceded(sp, char('}')),
            )),
        ),
    )
    .parse(i)
}

fn json_value<'a, E: ParseError<&'a str> + ContextError<&'a str>>(
    i: &'a str,
) -> IResult<&'a str, JsonValue, E> {
    preceded(
        sp,
        alt((
            map(hash, JsonValue::Object),
            map(array, JsonValue::Array),
            map(string, JsonValue::Str),
            map(double, JsonValue::Num),
            map(boolean, JsonValue::Boolean),
            map(null, |_| JsonValue::Null),
        )),
    )
    .parse(i)
}

pub fn root<'a, E: ParseError<&'a str> + ContextError<&'a str>>(
    i: &'a str,
) -> IResult<&'a str, JsonValue, E> {
    delimited(
        sp,
        alt((
            map(hash, JsonValue::Object),
            map(array, JsonValue::Array),
            map(null, |_| JsonValue::Null),
        )),
        opt(sp),
    )
    .parse(i)
}
