import { sqliteTable, text, integer } from 'drizzle-orm/sqlite-core';

// One row per repurpose job: a source link moving through the pipeline
//   pending → downloaded → generated → published   (or → error)
export const jobs = sqliteTable('jobs', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  sourceUrl: text('source_url').notNull(),
  sourcePlatform: text('source_platform'), // 'tiktok' | 'instagram' | 'youtube' | ...
  status: text('status').notNull().default('pending'),

  // Ingest output
  localPath: text('local_path'),           // downloaded mp4 on disk
  sourceCaption: text('source_caption'),   // original platform caption/description
  transcript: text('transcript'),          // Whisper transcript, when available

  // Claude-generated metadata
  title: text('title'),
  description: text('description'),
  tags: text('tags'),                      // JSON string[]
  hashtags: text('hashtags'),              // JSON string[]
  hook: text('hook'),

  // Publish output
  youtubeVideoId: text('youtube_video_id'),
  error: text('error'),

  createdAt: integer('created_at').notNull(),
  updatedAt: integer('updated_at').notNull(),
});

export type Job = typeof jobs.$inferSelect;
export type NewJob = typeof jobs.$inferInsert;
