//! AI assistance: this file was written with AI assistance. The maintainer reviewed it and did not find errors.
//!
//! Minimal marser JSON grammar for benchmarks: no recovery, no error annotations, no `Invalid` values.

use std::rc::Rc;

use marser::capture;
use marser::{
    matcher::{
        commit_matcher::commit_on,
        multiple::many,
        one_or_more::one_or_more,
        optional::optional,
        positive_lookahead,
    },
    one_of::one_of,
    parser::{deferred::recursive, token_parser::TokenParser, Parser, ParserCombinator},
};

#[derive(Debug, Clone, PartialEq)]
pub enum JsonValue {
    Null,
    Boolean(bool),
    Number(f64),
    String(String),
    Array(Vec<JsonValue>),
    Object(Vec<(String, JsonValue)>),
}

pub fn get_json_grammar<'src>() -> impl Parser<'src, &'src str, Output = JsonValue> + Clone {
    recursive(|element| {
        let ws = Rc::new(many(one_of((' ', '\t', '\n', '\r'))));

        let null = capture!(("null", ws.clone()) => JsonValue::Null);
        let boolean = one_of((
            capture!(("false", ws.clone()) => JsonValue::Boolean(false)),
            capture!(("true", ws.clone()) => JsonValue::Boolean(true)),
        ));

        let number = capture!(
            commit_on(
                positive_lookahead(one_of(('-', '0'..='9'))),
                bind_slice!((
                    optional('-'),
                    one_of(('0', ('1'..='9', many('0'..='9')))),
                    optional(('.', one_or_more('0'..='9'))),
                    optional((
                        one_of(('e', 'E')),
                        optional(one_of(('+', '-'))),
                        one_or_more('0'..='9')
                    )),
                ), slice as &'src str)
            ) => JsonValue::Number(slice.parse().unwrap_or(0.0))
        );

        let character = Rc::new(TokenParser::new(
            |c| *c != '"' && *c != '\\' && (*c as u32) >= 0x20,
            |x| *x,
        ));
        let hex_digit = Rc::new(one_of(('0'..='9', 'a'..='f', 'A'..='F')));
        let escaped_char = capture!({
            ('\\', bind!(one_of(('\"', '\\', '/', 'b', 'f', 'n', 'r', 't')), esc))
        } => {
            match esc {
                '"' => '"',
                '\\' => '\\',
                '/' => '/',
                'b' => '\u{0008}',
                'f' => '\u{000C}',
                'n' => '\n',
                'r' => '\r',
                't' => '\t',
                _ => esc,
            }
        });
        let unicode_escape = capture!({
            (
                '\\',
                'u',
                bind!(hex_digit.clone(), d1),
                bind!(hex_digit.clone(), d2),
                bind!(hex_digit.clone(), d3),
                bind!(hex_digit.clone(), d4),
            )
        } => {
            let hex: String = [d1, d2, d3, d4].into_iter().collect();
            let codepoint = u32::from_str_radix(&hex, 16).unwrap_or(0xFFFD);
            std::char::from_u32(codepoint).unwrap_or('\u{FFFD}')
        });
        let raw_string = Rc::new(
            capture!({
                (
                    '"',
                    many(one_of((
                        bind!(character.clone(), *chars),
                        bind!(escaped_char, *chars),
                        bind!(unicode_escape, *chars),
                    ))),
                    '"',
                    ws.clone(),
                )
            } => chars.into_iter().collect::<String>())
                .erase_types(),
        );

        let string = raw_string.clone().map_output(JsonValue::String);

        let array = capture!({
            (
                '[',
                ws.clone(),
                optional((
                    bind!(element.clone(), *elements),
                    many((',', ws.clone(), bind!(element.clone(), *elements))),
                )),
                ws.clone(),
                ']',
                ws.clone(),
            )
        } => JsonValue::Array(elements))
        .erase_types();

        let key_value_pair = Rc::new(
            capture!({
                (
                    bind!(raw_string.clone(), key),
                    ':',
                    ws.clone(),
                    bind!(element.clone(), value),
                )
            } => (key, value))
                .erase_types(),
        );

        let object = capture!({
            (
                '{',
                ws.clone(),
                optional((
                    bind!(key_value_pair.clone(), *pairs),
                    many((',', ws.clone(), bind!(key_value_pair.clone(), *pairs))),
                )),
                ws.clone(),
                '}',
                ws.clone(),
            )
        } => JsonValue::Object(pairs))
        .erase_types();

        capture!({
            (
                ws.clone(),
                bind!(
                    one_of((object, array, string, number, boolean, null)),
                    result
                ),
                ws.clone(),
            )
        } => result)
    })
}
