---
layout: default
title: Music
permalink: /music/
---

<div class="main-content">
  <ul class="post-list">
    {% assign sorted_music = site.music | sort: "date" | reverse %}
    {% for track in sorted_music %}
      <li>
        <div class="post-item">
          {% if track.date %}
          <span class="post-date">{{ track.date | date: "%Y.%m.%d" }}</span>
          {% endif %}
          <a class="post-title" href="{{ track.url | relative_url }}">{{ track.title }}</a>
          {% if track.artist %}
          <span class="post-meta">by {{ track.artist }}</span>
          {% endif %}
        </div>
      </li>
    {% endfor %}
  </ul>
</div>