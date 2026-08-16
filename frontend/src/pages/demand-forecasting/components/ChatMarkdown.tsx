import ReactMarkdown, {
  type Components,
} from 'react-markdown'
import remarkGfm from 'remark-gfm'

import {
  Anchor,
  Blockquote,
  Code,
  List,
  Table,
  Text,
} from '@mantine/core'

interface ChatMarkdownProps {
  content: string
}

// Protocols allowed for a rendered link's href - explicitly excludes
// javascript:/data:/vbscript: and anything else not on this list, per
// the chatbot integration's security requirement. Relative/hash links
// (no scheme at all) are allowed through as-is.
const SAFE_URL_PATTERN =
  /^(https?:|mailto:|tel:|#|\/(?!\/))/i

function toSafeHref(href: string | undefined): string | undefined {
  if (!href) {
    return undefined
  }

  return SAFE_URL_PATTERN.test(href.trim()) ? href : undefined
}

// Maps Markdown elements to real Mantine components so assistant
// messages inherit this app's existing typography/spacing/color
// tokens automatically, rather than introducing a separate stylesheet.
// No raw-HTML plugin (rehype-raw) is used anywhere in this module -
// react-markdown's default behavior already treats any literal HTML
// inside a Gemini response as plain escaped text, never executed
// markup, and this component never uses dangerouslySetInnerHTML.
// Headings are deliberately kept small (Text, not Title) since a
// full-size h1/h2 would overwhelm an 85%-width chat bubble.
const components: Components = {
  p: ({ children }) => (
    <Text size="sm" mb={6}>
      {children}
    </Text>
  ),
  h1: ({ children }) => (
    <Text size="md" fw={700} mt={4} mb={4}>
      {children}
    </Text>
  ),
  h2: ({ children }) => (
    <Text size="sm" fw={700} mt={4} mb={4}>
      {children}
    </Text>
  ),
  h3: ({ children }) => (
    <Text size="sm" fw={600} mt={4} mb={2}>
      {children}
    </Text>
  ),
  h4: ({ children }) => (
    <Text size="sm" fw={600} mt={4} mb={2}>
      {children}
    </Text>
  ),
  strong: ({ children }) => (
    <Text component="strong" fw={700} size="sm">
      {children}
    </Text>
  ),
  em: ({ children }) => (
    <Text component="em" fs="italic" size="sm">
      {children}
    </Text>
  ),
  ul: ({ children }) => (
    <List size="sm" withPadding mb={6}>
      {children}
    </List>
  ),
  ol: ({ children }) => (
    <List
      size="sm"
      withPadding
      type="ordered"
      mb={6}
    >
      {children}
    </List>
  ),
  li: ({ children }) => (
    <List.Item>{children}</List.Item>
  ),
  code: ({ className, children }) => {
    // A fenced block (```lang) carries a language className from
    // remark - render it as a scrollable block; a bare `inline code`
    // span has none, and stays inline.
    const isBlock = Boolean(className)

    return (
      <Code block={isBlock}>
        {String(children).replace(/\n$/, '')}
      </Code>
    )
  },
  a: ({ href, children }) => {
    const safeHref = toSafeHref(href)

    return (
      <Anchor
        href={safeHref}
        target="_blank"
        rel="noopener noreferrer"
        size="sm"
      >
        {children}
      </Anchor>
    )
  },
  blockquote: ({ children }) => (
    <Blockquote p="xs" mb={6}>
      {children}
    </Blockquote>
  ),
  table: ({ children }) => (
    <Table.ScrollContainer
      minWidth={280}
      mb={6}
    >
      <Table
        striped
        withTableBorder
        withColumnBorders
        verticalSpacing={4}
      >
        {children}
      </Table>
    </Table.ScrollContainer>
  ),
  thead: ({ children }) => (
    <Table.Thead>{children}</Table.Thead>
  ),
  tbody: ({ children }) => (
    <Table.Tbody>{children}</Table.Tbody>
  ),
  tr: ({ children }) => (
    <Table.Tr>{children}</Table.Tr>
  ),
  th: ({ children }) => (
    <Table.Th>{children}</Table.Th>
  ),
  td: ({ children }) => (
    <Table.Td>{children}</Table.Td>
  ),
}

const ChatMarkdown = ({ content }: ChatMarkdownProps) => {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={components}
    >
      {content}
    </ReactMarkdown>
  )
}

export default ChatMarkdown
