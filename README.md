## What is scan-organizer?

I scan each and every piece of paper that passes through my hands. All my old to-do lists, bills people send me in the mail, the manual for my microwave, everything. I have a lot of scans.

**scan-organizer** is a tool I wrote to help me neatly organize and label everything, and make it searchable. It's designed for going through a huge backlog by hand over the course of weeks, and then dumping a new set of raw scans in whenever afterwards. I have a specific processing pipeline discussed below. However if you have even a little programming skill, I've designed this to be modified to suit your own workflow.

## Input and output

The input is some raw scans. They could be handwritten notes, printed computer documents, photos, or whatever.

![A movie ticket stub](/screenshots/sample_image.jpg)

The final product is that for each file like `ticket.jpg`, one ends up with `ticket.txt`. This has metadata about the file (tags, category, notes) and a transcription of any text in the image, to make it searchable.

```
---
category: movie tickets
filename: seven psychopaths ticket.jpg
tags:
- cleaned
- categorized
- named
- hand_transcribe
- transcribed
- verified
---
Rialto Cinemas Elmwood
SEVEN PSYCHOPAT
R
Sun Oct 28 1
7:15 PM
Adult $10.50
00504-3102812185308

Rialto Cinemas Gift Cards
Perfect For Movie Lovers!
```

Here are some screenshots of my personal process.

### Phase 1: Rotating and Cropping
![Phase 1: Rotating and Cropping](/screenshots/phase1.png)

First, I clean up the images. Crop them, rotate them if they're not facing the right way. I can rotate images with the buttons at the bottom, or with keyboard shortcuts. Once I'm done, I press a button, and *scan-organizer* advanced to the next un-cleaned photo. At any point, I can exit the program, and all progress is saved.

### Phase 2: Sorting into folders
![Phase 2: Sorting into folders](/screenshots/phase2.png)

Next, I sort things into folders, or "categories". As I browse folders, I can preview what's already in that folder.

### Phase 3: Renaming Images
![Phase 3: Renaming images](/screenshots/phase3.png)

Renaming images comes next. For convenience, I can browse existing images in the folder, to help name everything in a standard way.

### Phase 4: Tagging images
![Phase 4: Tagging images](/screenshots/phase4.png)

I tag my images with the type of text. They might be handwritten. Or they might be printed computer documents. You can imagine extending the process with other types of tagging for your use case.

### Not done: OCR
Printed documents are run through OCR. This isn't actually done yet, but it will be easy to plug in. I'll use tesseract.

### Phase 5: Transcribing by hand
![Phase 5a: Transcribing by Hand](/screenshots/phase5.png)

I type up all my handwritten documents. I have not found any useful handwriting recognition software. I just type it all by hand. For screenshot readability, the screenshot is actually of a printed document.

### Phase 6: Verification
![Phase 6: Verification](/screenshots/phase6.png)
At the end of the whole process, I verify that each image looks good, is correctly tagged and transcribed, and so on.

## Alternatives
If you want an AI-powered, 80% accurate, webservice-with-APIs, docker solution, you're not me. I've heard of [paperless-ngx](https://github.com/paperless-ngx/paperless-ngx).
