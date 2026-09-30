// funcspan reports the byte span and shape of one method declaration.
//
//	funcspan <file.go> <Receiver> <Method>
//
// Output (JSON): start/end byte offsets of the declaration (including its doc
// comment), the header text (receiver, name, signature), the doc comment, and
// counts of constructs inside the body.
package main

import (
	"encoding/json"
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
)

type result struct {
	Found       int            `json:"found"`
	Start       int            `json:"start"`
	End         int            `json:"end"`
	Header      string         `json:"header"`
	Doc         string         `json:"doc"`
	Calls       map[string]int `json:"calls"`
	Idents      map[string]int `json:"idents"`
	Loops       int            `json:"loops"`
	GoStmts     int            `json:"go_stmts"`
	FuncLits    int            `json:"func_lits"`
	Nodes       int            `json:"nodes"`
	StringLits  []string       `json:"string_lits"`
	ImportsText string         `json:"imports"`
}

func receiverName(fd *ast.FuncDecl) string {
	if fd.Recv == nil || len(fd.Recv.List) != 1 {
		return ""
	}
	switch t := fd.Recv.List[0].Type.(type) {
	case *ast.StarExpr:
		if id, ok := t.X.(*ast.Ident); ok {
			return "*" + id.Name
		}
	case *ast.Ident:
		return t.Name
	}
	return ""
}

func main() {
	if len(os.Args) != 4 {
		fmt.Fprintln(os.Stderr, "usage: funcspan <file.go> <Receiver> <Method>")
		os.Exit(2)
	}
	src, err := os.ReadFile(os.Args[1])
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	fset := token.NewFileSet()
	file, err := parser.ParseFile(fset, os.Args[1], src, parser.ParseComments)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(3)
	}
	res := result{Calls: map[string]int{}, Idents: map[string]int{}, StringLits: []string{}}
	off := func(p token.Pos) int { return fset.Position(p).Offset }
	for _, decl := range file.Decls {
		fd, ok := decl.(*ast.FuncDecl)
		if !ok || fd.Name.Name != os.Args[3] || receiverName(fd) != os.Args[2] {
			continue
		}
		res.Found++
		start := fd.Pos()
		if fd.Doc != nil {
			start = fd.Doc.Pos()
			res.Doc = fd.Doc.Text()
		}
		res.Start = off(start)
		res.End = off(fd.End())
		res.Header = string(src[off(fd.Pos()):off(fd.Body.Lbrace)])
		ast.Inspect(fd.Body, func(n ast.Node) bool {
			if n == nil {
				return false
			}
			res.Nodes++
			switch x := n.(type) {
			case *ast.CallExpr:
				switch f := x.Fun.(type) {
				case *ast.SelectorExpr:
					res.Calls[f.Sel.Name]++
				case *ast.Ident:
					res.Calls[f.Name]++
				}
			case *ast.Ident:
				res.Idents[x.Name]++
			case *ast.ForStmt, *ast.RangeStmt:
				res.Loops++
			case *ast.GoStmt:
				res.GoStmts++
			case *ast.FuncLit:
				res.FuncLits++
			case *ast.BasicLit:
				if x.Kind == token.STRING {
					res.StringLits = append(res.StringLits, x.Value)
				}
			}
			return true
		})
	}
	if len(file.Imports) > 0 {
		first := file.Decls[0]
		res.ImportsText = string(src[off(first.Pos()):off(first.End())])
	}
	out, _ := json.Marshal(res)
	fmt.Println(string(out))
}
