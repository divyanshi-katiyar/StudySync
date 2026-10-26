/** Each subject gets a spine colour so groups are recognisable at a glance (never the only cue: the name is always shown). */
export const SUBJECT_COLORS = {
  'Data Structures': '#0F7B70',
  Databases: '#6446C9',
  'Operating Systems': '#B4540B',
  'Web Development': '#1D6FA5',
  Placements: '#2F7D32',
  'AI and ML': '#B8325A',
  Compilers: '#7A5C00',
  Networks: '#3B5BA9',
}
export const SUBJECTS = Object.keys(SUBJECT_COLORS)
export const subjectColor = (subject) => SUBJECT_COLORS[subject] ?? '#4F5A73'
