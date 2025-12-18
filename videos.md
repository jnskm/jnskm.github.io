---
layout: default
title: Videos
permalink: /videos/
---

<div class="main-content">
  <ul class="post-list">
    {% assign sorted_videos = site.videos | sort: "date" | reverse %}
    {% for video in sorted_videos %}
      <li>
        <div class="post-item">
          {% if video.date %}
          <span class="post-date">{{ video.date | date: "%Y.%m.%d" }}</span>
          {% endif %}
          <a class="post-title" href="{{ video.url | relative_url }}">{{ video.title }}</a>
        </div>
      </li>
    {% endfor %}
  </ul>
</div>

