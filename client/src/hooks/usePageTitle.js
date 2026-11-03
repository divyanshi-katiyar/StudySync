import { useEffect } from 'react'

/** Sets the document title so each view is announced and listed correctly in the browser history. */
export function usePageTitle(title) {
  useEffect(() => {
    document.title = title ? `${title} - StudySync` : 'StudySync'
  }, [title])
}
