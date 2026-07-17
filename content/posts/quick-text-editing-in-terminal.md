+++
date = '2026-07-17T12:25:56+01:00'
draft = false
title = 'Writing easily accessible text from your terminal'
description = 'A 5-line shell function that replaced my Sublime Text detour and scratched the itch of doing less with more.'
tags = ['Terminal', 'Editing', 'Vim', 'Text']
categories = ['Terminal']
+++

A shell function I wrote to stop reaching for Sublime Text every time I need to write a Slack message.

<!--more-->

## The Itch

The further I go in my career, the more obsessed I get with shaving steps off things that mildly annoy me. It's a sickness, and I've made peace with it.

## The Problem

At work, I juggle three things all day: my terminal, my IDE, and Slack.

Slack is the weak link. As a Vim user, editing messages is a pain — navigating text with arrow keys and no modal editing makes me feel like I've forgotten how to type. So I'd do this:

1. Open Sublime Text (vim mode, no save required)
2. Open a new tab
3. Write and polish the text
4. Select all, copy
5. Close the tab (maybe)
6. Send the message

Cumbersome. Four tools open just to write a Slack message.

So I wrote this:

{{< code bash >}}

# in your ~/.zshrc

s() {
  local f
  f=$(mktemp /tmp/scratch.XXXXXX)
  vi "$f"
  cat "$f" | pbcopy
  rm -f "$f"
}

{{< /code >}}

Now it's:

1. Type `s` in the terminal
2. Write and edit the text in Vim
3. Close the file — it's already in your clipboard
4. Send the message

## "That's it?"

Yes. Two steps fewer, one tool fewer, zero context switching.

I know it sounds absurdly small. But small friction compounds. Every time you reach for a separate tool, you break flow, lose a few seconds, and add just enough overhead that you sometimes just... don't bother refining what you're writing.

This little function removed that resistance entirely.

If you have a similar itch, here's a challenge: what other tools in your workflow could be replaced by a scratch buffer and a copy to clipboard?
