export interface SpotifyAlbum {
  id: string
  name: string
  artists: Array<{ id: string; name: string }>
  images: Array<{ url: string; width: number; height: number }>
  release_date: string
  genres: string[]
  tracks?: {
    items: SpotifyTrack[]
    total: number
  }
  total_tracks?: number
  external_urls?: { spotify: string }
}

export interface SpotifyTrack {
  id: string
  name: string
  duration_ms: number
  track_number: number
  artists: Array<{ id: string; name: string }>
  preview_url: string | null
  external_urls?: { spotify: string }
}

export interface Album {
  id: string
  title: string
  artistName: string
  artistId: string
  releaseYear: number
  coverUrl: string | null
  genres: string[]
  avgRating: number | null
  ratingCount: number
}

export interface Review {
  id: string
  userId: string
  albumId: string
  body: string
  rating: number | null
  likes: number
  createdAt: string
  updatedAt: string
  user: {
    id: string
    username: string
    avatarUrl: string | null
  }
}

export interface Rating {
  id: string
  userId: string
  albumId: string
  value: number
  createdAt: string
}

export interface UserProfile {
  id: string
  username: string
  email: string
  avatarUrl: string | null
  bio: string | null
  createdAt: string
  _count?: {
    ratings: number
    reviews: number
    following: number
    followers: number
  }
}

export interface AlbumWithReviews extends Album {
  reviews: Review[]
  tracks?: SpotifyTrack[]
  spotifyUrl?: string
}

export interface SessionUser {
  id: string
  username: string
  email: string
  avatarUrl?: string | null
}
