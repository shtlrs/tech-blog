+++
date = '2026-09-21T14:13:56+01:00'
draft = false
title = 'How git distributes files across "random" directories'
tags = ['Terminal', 'Git', 'Version Control']
categories = ['Terminal', 'Version Control', 'Git']
+++

In the [first post]({{< relref "inside-git-object-storage" >}}) of this series,
I mentioned that `git` distributes its objects across multiple directories, chosen in a specific way.

In this post, we'll look at how and why `git` creates them.

<!--more-->

## How we'd imagine things

When I didn't know how git worked, I kinda imagined that it'd replicate the structure of what I'm tracking in its database.

Meaning, if I had a repo like this

```tree
my_project/
├── photos/
│   ├── mountain.png
│   └── river.png
└── documents/
    ├── report.pdf
    └── resume.pdf
```

I would have imagined `git` to create the `photos` and `documents` directories, and save a copy of all the tracked files
in their respective directories, but that's not how it works.

So what does it do then ?

## The `.git/objects` anatomy

`git` stores everything into the `.git/objects` directory. Beyond two bookkeeping dirs (`info` and `pack`, out of scope here),
the only other entries you'll ever find there are directories whose name is a 2-character hexadecimal string.

Which raises the question: why?

## Directory names are also based on file content

We've seen that each file is tracked as a `blob`, and each `blob` has a unique hash based on the content of the file itself.

Say that `blob`'s hash is the `e9ab4ccbecf1565f28381c1154d65c15409ad181` string.
What git does is:

* Take the first 2 characters of that hash: `e9`
* Create a directory under `.git/objects` with that value
* Take the rest of the string `ab4ccbecf1565f28381c1154d65c15409ad181` and create a file with that name under `e9`

So we can see here that the directory name is dictated by the `blob`'s hash, which is based on the file content, leading
to the conclusion that directory names are also based on the file content.

But why does `git` do this ?

## The performance reason

Most file systems don't like having too many files in one directory, and as the number of files in one place grows,
file lookups and some file-related operations will become way too slow.

To avoid this, `git` distributes files across `256` intermediary directories whose name is the first 2 characters
of each file's final hash.

That `256` value stems from the fact that, since it's only a 2-character hexadecimal string, it means the name
can only contain the values: 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, a, b, c, d, e, f.

That's 16 possible characters, repeatable twice: `16^2 = 256`.

This means that the `.git/objects` directory, aside from those `pack` and `info` directories, will never have more than
256 other ones.

## A concrete example

In my company, we have a giant monolith with over 1M files, but if we inspect the `.git/objects` directory, we'll see:

```text
00      0f      1e      2d      3c      4b      5a      69      78      87      96      a5      b4      c3      d2      e1      f0      ff
01      10      1f      2e      3d      4c      5b      6a      79      88      97      a6      b5      c4      d3      e2      f1      info
02      11      20      2f      3e      4d      5c      6b      7a      89      98      a7      b6      c5      d4      e3      f2      pack
03      12      21      30      3f      4e      5d      6c      7b      8a      99      a8      b7      c6      d5      e4      f3
04      13      22      31      40      4f      5e      6d      7c      8b      9a      a9      b8      c7      d6      e5      f4
05      14      23      32      41      50      5f      6e      7d      8c      9b      aa      b9      c8      d7      e6      f5
06      15      24      33      42      51      60      6f      7e      8d      9c      ab      ba      c9      d8      e7      f6
07      16      25      34      43      52      61      70      7f      8e      9d      ac      bb      ca      d9      e8      f7
08      17      26      35      44      53      62      71      80      8f      9e      ad      bc      cb      da      e9      f8
09      18      27      36      45      54      63      72      81      90      9f      ae      bd      cc      db      ea      f9
0a      19      28      37      46      55      64      73      82      91      a0      af      be      cd      dc      eb      fa
0b      1a      29      38      47      56      65      74      83      92      a1      b0      bf      ce      dd      ec      fb
0c      1b      2a      39      48      57      66      75      84      93      a2      b1      c0      cf      de      ed      fc
0d      1c      2b      3a      49      58      67      76      85      94      a3      b2      c1      d0      df      ee      fd
0e      1d      2c      3b      4a      59      68      77      86      95      a4      b3      c2      d1      e0      ef      fe
```

As you can see above, we've exhausted all the directory names possible, going all the way from `00` to `ff`, making a total
of 256 directories.

## Try it yourself

You don't need a giant monolith to see this in action. Here's what happens on a fresh repo:

```bash
mkdir demo-repo && cd demo-repo
git init
echo "hello" > hello.txt
git add hello.txt
ls .git/objects
```

Output:

```text
ce      info    pack
```

One hash-based directory, `ce`, because we've only added one file. Inside it:

```bash
ls .git/objects/ce
```

```text
013625030ba8dba906f756967f9e9ca394464a
```

That 38-character filename combined with the `ce` prefix gives you the full SHA-1 hash of the blob: `ce013625030ba8dba906f756967f9e9ca394464a`.
Add more files and more directories appear — once the project is large enough, all 256 slots will be filled.

---

That's the whole trick: use the first 2 characters of the hash as a bucket. No matter how large a repository grows,
`.git/objects` never holds more than 256 subdirectories, keeping filesystem operations fast.
