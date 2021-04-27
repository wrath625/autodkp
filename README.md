# autodkp

## Installation
`pip install -r requirements.txt`

## Usage
`python main.py <username> <website password>`

Currently the OCR chat parsing window is hard coded to 
```
screen_rect = [
    5,     # x
    1128,   # y
    616,    # width
    275     # height
]
```

You will need to change this in the `read_chat` function if you use something other than ElvUI at 2160p